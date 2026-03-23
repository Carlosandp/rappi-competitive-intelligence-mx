"""
report_generator.py — Generates a self-contained HTML executive report.
Includes Chart.js bar charts, KPI cards, insight cards, and comparison tables.
Everything in English. No external dependencies beyond Chart.js CDN.
"""
from __future__ import annotations

import sys
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "analysis"))
sys.path.insert(0, str(BASE_DIR / "scrapers"))

from normalize import normalize_dataset, get_summary_stats
from insights import generate_insights

PLATFORM_COLORS = {
    "rappi":     "#FF441F",
    "uber":      "#06C167",
    "didi":      "#FF6B00",
    "Rappi":     "#FF441F",
    "Uber Eats": "#06C167",
    "DiDi Food": "#FF6B00",
}
SEV_COLORS = {"high": "#EF4444", "medium": "#F59E0B", "low": "#22C55E"}
SEV_LABELS = {"high": "High Priority", "medium": "Medium Priority", "low": "Low Priority"}


def _df_to_html_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    rows = "".join(
        "<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>"
        for row in df.values
    )
    headers = "".join(f"<th>{c}</th>" for c in df.columns)
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>"


def _chartjs_bar(canvas_id, labels, datasets, y_prefix="", y_suffix="", title="", height=280):
    ds_json     = json.dumps(datasets)
    labels_json = json.dumps(labels)
    p_js = f"'{y_prefix}' + " if y_prefix else ""
    s_js = f" + '{y_suffix}'"  if y_suffix else ""
    title_js = title.replace("'", "\\'")
    return f"""
<div style="background:#1E293B;border:1px solid #334155;border-radius:12px;padding:20px;margin:16px 0;">
  <canvas id="{canvas_id}" height="{height}"></canvas>
</div>
<script>
(function(){{
  var ctx=document.getElementById('{canvas_id}').getContext('2d');
  new Chart(ctx,{{
    type:'bar',
    data:{{labels:{labels_json},datasets:{ds_json}}},
    options:{{
      responsive:true,
      plugins:{{
        title:{{display:{'true' if title else 'false'},text:'{title_js}',color:'#F8FAFC',font:{{size:15,weight:'bold'}}}},
        legend:{{labels:{{color:'#F8FAFC',font:{{size:12}}}}}},
        tooltip:{{callbacks:{{label:function(c){{return c.dataset.label+': '+{p_js}c.parsed.y.toFixed(0){s_js};}}}}}}
      }},
      scales:{{
        x:{{ticks:{{color:'#CBD5E1'}},grid:{{color:'rgba(148,163,184,0.15)'}}}},
        y:{{ticks:{{color:'#CBD5E1',callback:function(v){{return {p_js}v.toFixed(0){s_js};}}}},
           grid:{{color:'rgba(148,163,184,0.15)'}},beginAtZero:true}}
      }}
    }}
  }});
}})();
</script>"""


def generate_html_report(df_raw: pd.DataFrame, output_path: Path = None) -> str:
    df      = normalize_dataset(df_raw)
    stats   = get_summary_stats(df)
    insights = generate_insights(df)
    now     = datetime.now().strftime("%d %b %Y, %H:%M")
    fdf     = df[df["has_price"]]

    platforms = ["Rappi", "Uber Eats", "DiDi Food"]
    colors    = [PLATFORM_COLORS[p] for p in platforms]
    products  = sorted(fdf["product_canonical"].unique())

    # ── Chart datasets ────────────────────────────────────────────────────
    price_pivot = (
        fdf.groupby(["platform_label","product_canonical"])["product_price"]
        .mean().unstack(fill_value=0).round(2)
    )
    price_datasets = [
        {"label": p,
         "data": [float(price_pivot.loc[p, prod]) if p in price_pivot.index and prod in price_pivot.columns else 0
                  for prod in products],
         "backgroundColor": PLATFORM_COLORS[p]}
        for p in platforms
    ]

    fee_by_plat  = fdf.groupby("platform_label")["delivery_fee"].mean().round(2)
    fee_datasets = [{"label": "Avg Delivery Fee (MXN)",
                     "data": [float(fee_by_plat.get(p, 0)) for p in platforms],
                     "backgroundColor": colors}]

    eta_by_plat  = fdf[fdf["eta_midpoint"].notna()].groupby("platform_label")["eta_midpoint"].mean().round(1)
    eta_datasets = [{"label": "Avg ETA (min)",
                     "data": [float(eta_by_plat.get(p, 0)) for p in platforms],
                     "backgroundColor": colors}]

    promo_base   = fdf[fdf["discount_visible"].notna()]
    promo_by_plat = (promo_base.groupby("platform_label")["discount_visible"].mean() * 100).round(1)
    promo_datasets = [{"label": "Promo Visibility (%)",
                       "data": [float(promo_by_plat.get(p, 0)) for p in platforms],
                       "backgroundColor": colors}]

    valid_et = fdf[fdf["effective_total"].notna() & (fdf["effective_total"] > 20)]
    tot_pivot = (
        valid_et.groupby(["platform_label","product_canonical"])["effective_total"]
        .mean().unstack(fill_value=0).round(2)
    )
    total_datasets = [
        {"label": p,
         "data": [float(tot_pivot.loc[p, prod]) if p in tot_pivot.index and prod in tot_pivot.columns else 0
                  for prod in products],
         "backgroundColor": PLATFORM_COLORS[p]}
        for p in platforms
    ]

    # ── Summary tables ────────────────────────────────────────────────────
    price_tbl = fdf.groupby(["platform_label","product_canonical"])["product_price"].mean().reset_index()
    price_tbl.columns = ["Platform","Product","Avg Price (MXN)"]
    price_tbl["Avg Price (MXN)"] = price_tbl["Avg Price (MXN)"].round(2)

    fee_tbl = fdf.groupby(["platform_label","zone_type"])["delivery_fee"].mean().reset_index()
    fee_tbl.columns = ["Platform","Zone Type","Avg Delivery Fee (MXN)"]
    fee_tbl["Avg Delivery Fee (MXN)"] = fee_tbl["Avg Delivery Fee (MXN)"].round(2)

    eta_tbl = fdf[fdf["eta_midpoint"].notna()].groupby("platform_label")["eta_midpoint"].agg(
        ["mean","min","max"]).reset_index()
    eta_tbl.columns = ["Platform","Avg ETA (min)","Min ETA","Max ETA"]
    eta_tbl = eta_tbl.round(1)

    promo_tbl = promo_by_plat.reset_index()
    promo_tbl.columns = ["Platform","Promo Rate (%)"]

    # ── KPIs ──────────────────────────────────────────────────────────────
    r_price = stats.get("avg_price_rappi", 0) or 0
    u_price = stats.get("avg_price_uber",  0) or 0
    d_price = stats.get("avg_price_didi",  0) or 0
    r_eta   = stats.get("avg_eta_rappi",   0) or 0
    u_eta   = stats.get("avg_eta_uber",    0) or 0
    d_eta   = stats.get("avg_eta_didi",    0) or 0
    r_fee   = stats.get("avg_delivery_fee_rappi", 0) or 0
    u_fee   = stats.get("avg_delivery_fee_uber",  0) or 0
    d_fee   = stats.get("avg_delivery_fee_didi",  0) or 0
    r_promo = (stats.get("promo_rate_rappi", 0) or 0) * 100
    u_promo = (stats.get("promo_rate_uber",  0) or 0) * 100
    d_promo = (stats.get("promo_rate_didi",  0) or 0) * 100

    # ── Insight cards ─────────────────────────────────────────────────────
    insight_cards = ""
    for ins in insights:
        sev   = ins.get("severity", "medium")
        color = SEV_COLORS[sev]
        data_html = _df_to_html_table(ins.get("data")) if isinstance(ins.get("data"), pd.DataFrame) else ""
        insight_cards += f"""
        <div class="insight-card" style="border-left-color:{color};">
          <div class="insight-header">
            <span class="insight-num">#{ins['id']}</span>
            <span class="insight-cat">{ins['category']}</span>
            <span class="insight-sev" style="background:{color}20;color:{color};">{SEV_LABELS[sev]}</span>
          </div>
          <h3>{ins['title']}</h3>
          <div class="insight-section">
            <div class="insight-label">FINDING</div>
            <p>{ins['finding']}</p>
          </div>
          <div class="insight-section">
            <div class="insight-label">IMPACT</div>
            <p>{ins['impact']}</p>
          </div>
          <div class="insight-section">
            <div class="insight-label">RECOMMENDATION</div>
            <p class="recommendation">{ins['recommendation']}</p>
          </div>
          {f'<details><summary>View supporting data</summary>{data_html}</details>' if data_html else ''}
        </div>"""

    # ── Full HTML ─────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Executive Report -- Competitive Intelligence Rappi</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Inter',-apple-system,sans-serif;background:#0F172A;color:#F8FAFC;line-height:1.6;}}
  .container{{max-width:1100px;margin:0 auto;padding:40px 24px;}}
  .header{{background:linear-gradient(135deg,#FF441F 0%,#FF6B4A 100%);border-radius:16px;padding:40px;margin-bottom:40px;}}
  .header h1{{font-size:2rem;font-weight:800;color:white;margin-bottom:8px;}}
  .header p{{color:rgba(255,255,255,0.85);font-size:1rem;}}
  .meta{{display:flex;gap:12px;margin-top:16px;flex-wrap:wrap;}}
  .meta span{{background:rgba(255,255,255,0.15);padding:4px 12px;border-radius:20px;font-size:0.82rem;color:white;}}
  h2{{font-size:1.4rem;font-weight:700;margin:40px 0 20px;padding-bottom:10px;border-bottom:2px solid #FF441F;}}
  .sub{{font-size:1rem;font-weight:600;color:#94A3B8;margin:24px 0 12px;}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:32px;}}
  .kpi-card{{background:#1E293B;border:1px solid #334155;border-radius:12px;padding:20px;text-align:center;}}
  .kpi-plat{{font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;}}
  .kpi-val{{font-size:2.2rem;font-weight:800;margin-bottom:4px;}}
  .kpi-lbl{{font-size:0.75rem;color:#94A3B8;margin-bottom:12px;}}
  .kpi-det{{font-size:0.8rem;color:#94A3B8;line-height:1.9;}}
  table{{width:100%;border-collapse:collapse;margin:16px 0;background:#1E293B;border-radius:10px;overflow:hidden;}}
  th{{background:#0F172A;padding:10px 14px;font-size:0.78rem;text-align:left;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px;}}
  td{{padding:10px 14px;font-size:0.88rem;border-bottom:1px solid #334155;}}
  tr:last-child td{{border-bottom:none;}}
  tr:hover td{{background:#334155;}}
  .chart-row{{display:grid;grid-template-columns:1fr 1fr;gap:16px;}}
  .insight-card{{background:#1E293B;border-left:4px solid;border-radius:0 12px 12px 0;padding:20px 24px;margin-bottom:24px;}}
  .insight-header{{display:flex;align-items:center;gap:12px;margin-bottom:12px;}}
  .insight-num{{font-size:1.5rem;font-weight:800;color:#FF441F;}}
  .insight-cat{{font-size:0.78rem;font-weight:700;background:#334155;padding:3px 10px;border-radius:20px;color:#CBD5E1;}}
  .insight-sev{{font-size:0.78rem;font-weight:700;padding:3px 10px;border-radius:20px;}}
  .insight-card h3{{font-size:1.05rem;font-weight:700;margin-bottom:14px;}}
  .insight-section{{margin-bottom:12px;}}
  .insight-label{{font-size:0.72rem;font-weight:700;letter-spacing:1px;color:#94A3B8;margin-bottom:4px;}}
  .insight-section p{{font-size:0.88rem;color:#CBD5E1;}}
  .recommendation{{color:#F8FAFC!important;font-weight:500;}}
  details{{margin-top:12px;}} summary{{cursor:pointer;font-size:0.82rem;color:#94A3B8;}}
  .badge-row{{display:flex;gap:10px;margin-bottom:24px;flex-wrap:wrap;}}
  .badge{{background:#1E293B;border:1px solid #334155;border-radius:8px;padding:8px 14px;font-size:0.82rem;color:#CBD5E1;}}
  .badge strong{{color:#F8FAFC;}}
  .footer{{text-align:center;font-size:0.75rem;color:#475569;margin-top:60px;padding-top:24px;border-top:1px solid #334155;}}
  @media(max-width:700px){{.kpi-grid,.chart-row{{grid-template-columns:1fr;}}}}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>Competitive Intelligence Report</h1>
    <p>Rappi vs Uber Eats vs DiDi Food &mdash; McDonald's Mexico</p>
    <div class="meta">
      <span>Generated: {now}</span>
      <span>{stats['addresses']} delivery addresses</span>
      <span>{stats['cities']} cities</span>
      <span>{stats['total_observations']:,} observations</span>
      <span>{stats['success_rate']:.0%} success rate</span>
    </div>
  </div>

  <h2>Executive Summary</h2>
  <div class="badge-row">
    <div class="badge">Coverage: <strong>CDMX, Guadalajara, Monterrey</strong></div>
    <div class="badge">Platforms: <strong>Rappi · Uber Eats · DiDi Food</strong></div>
    <div class="badge">Products: <strong>{stats['products']} McDonald's items</strong></div>
    <div class="badge">Insights: <strong>5 actionable findings</strong></div>
  </div>
  <p style="color:#CBD5E1;margin-bottom:24px;">
    Analysis covers <strong>{stats['addresses']} delivery addresses</strong> across CDMX, Guadalajara and Monterrey,
    comparing <strong>3 platforms</strong> on {stats['products']} key products. Five strategic insights
    were generated for Pricing and Strategy teams.
  </p>

  <h2>Platform Snapshot</h2>
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-plat" style="color:#FF441F;">Rappi</div>
      <div class="kpi-val" style="color:#FF441F;">${r_price:.0f}</div>
      <div class="kpi-lbl">Avg product price (MXN)</div>
      <hr style="border-color:#334155;margin:10px 0;">
      <div class="kpi-det">Delivery fee: <strong>${r_fee:.0f}</strong><br>Avg ETA: <strong>{r_eta:.0f} min</strong><br>Promo rate: <strong>{r_promo:.0f}%</strong></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-plat" style="color:#06C167;">Uber Eats</div>
      <div class="kpi-val" style="color:#06C167;">${u_price:.0f}</div>
      <div class="kpi-lbl">Avg product price (MXN)</div>
      <hr style="border-color:#334155;margin:10px 0;">
      <div class="kpi-det">Delivery fee: <strong>${u_fee:.0f}</strong><br>Avg ETA: <strong>{u_eta:.0f} min</strong><br>Promo rate: <strong>{u_promo:.0f}%</strong></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-plat" style="color:#FF6B00;">DiDi Food</div>
      <div class="kpi-val" style="color:#FF6B00;">${d_price:.0f}</div>
      <div class="kpi-lbl">Avg product price (MXN)</div>
      <hr style="border-color:#334155;margin:10px 0;">
      <div class="kpi-det">Delivery fee: <strong>${d_fee:.0f}</strong><br>Avg ETA: <strong>{d_eta:.0f} min</strong><br>Promo rate: <strong>{d_promo:.0f}%</strong></div>
    </div>
  </div>

  <h2>Pricing Analysis</h2>
  {_chartjs_bar("chart_price", products, price_datasets, y_prefix="$", title="Avg Product Price by Platform (MXN)")}
  <p class="sub">Price breakdown by product</p>
  {_df_to_html_table(price_tbl)}

  <h2>Total Cost to User</h2>
  {_chartjs_bar("chart_total", products, total_datasets, y_prefix="$", title="Estimated Total Cost — Product + Fees (MXN)")}
  <p style="font-size:0.82rem;color:#94A3B8;margin-top:8px;">Total = product price + delivery fee + service fee &minus; discounts</p>

  <h2>Fee Analysis</h2>
  <div class="chart-row">
    {_chartjs_bar("chart_fee", platforms, fee_datasets, y_prefix="$", title="Avg Delivery Fee (MXN)", height=220)}
    {_chartjs_bar("chart_promo", platforms, promo_datasets, y_suffix="%", title="Promo Visibility Rate (%)", height=220)}
  </div>
  <p class="sub">Delivery fee by zone type</p>
  {_df_to_html_table(fee_tbl)}

  <h2>Delivery Time (ETA)</h2>
  {_chartjs_bar("chart_eta", platforms, eta_datasets, y_suffix=" min", title="Avg ETA by Platform (minutes)", height=220)}
  {_df_to_html_table(eta_tbl)}

  <h2>Top 5 Competitive Insights</h2>
  <p style="color:#CBD5E1;margin-bottom:24px;">
    Actionable findings for <strong>Strategy</strong>, <strong>Pricing</strong> and <strong>Operations</strong> teams.
  </p>
  {insight_cards}

  <div class="footer">
    Auto-generated by the Competitive Intelligence Pipeline &mdash; Rappi Mexico &mdash; {now}<br>
    Data: McDonald's &bull; Rappi + Uber Eats + DiDi Food &bull; {stats['addresses']} delivery addresses
  </div>

</div>
</body>
</html>"""

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Report saved: {output_path}")
    return html


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE_DIR / "analysis"))
    sys.path.insert(0, str(BASE_DIR / "scrapers"))

    PROCESSED_DIR = BASE_DIR / "data" / "processed"
    REPORTS_DIR   = BASE_DIR / "reports"
    REPORTS_DIR.mkdir(exist_ok=True)

    csvs = sorted(PROCESSED_DIR.glob("competitive_prices_*.csv"), reverse=True)
    if not csvs:
        print("No data found. Run: python analysis/generate_demo_data.py")
        sys.exit(1)

    df_raw = pd.read_csv(csvs[0])
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORTS_DIR / f"competitive_intelligence_report_{ts}.html"
    generate_html_report(df_raw, out)
    generate_html_report(df_raw, REPORTS_DIR / "competitive_intelligence_report_latest.html")
    print("Done.")
