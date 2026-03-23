"""
dashboard.py -- Streamlit executive dashboard for Competitive Intelligence.
Python 3.9+ compatible. Streamlit 1.12+ compatible.

Tabs:
  1. Overview  -- KPI cards + summary table
  2. Pricing   -- Product price comparison
  3. Fees      -- Delivery fee + service fee analysis
  4. ETA       -- Delivery time comparison
  5. Promotions -- Discount frequency and labels
  6. Top 5 Insights -- Structured findings for Strategy & Pricing
  7. Evidence  -- Screenshots + filtered raw data
"""

from __future__ import annotations

import sys
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent.parent
for _p in [str(BASE_DIR / "analysis"), str(BASE_DIR / "scrapers"), str(BASE_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
import numpy as np
import streamlit as st

# -- Plotly import (optional -- graceful if missing) --------------------
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

st.set_page_config(
    page_title="Rappi Competitive Intelligence",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -- Design tokens ------------------------------------------------------
COLORS = {
    "rappi":   "#FF441F",
    "uber":    "#06C167",
    "didi":    "#FF6B00",
    "bg":      "#0F172A",
    "surface": "#1E293B",
    "text":    "#F8FAFC",
    "muted":   "#CBD5E1",
    "border":  "#334155",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "danger":  "#EF4444",
}
PLATFORM_COLORS = {
    "Rappi":     COLORS["rappi"],
    "Uber Eats": COLORS["uber"],
    "DiDi Food": COLORS["didi"],
}

st.markdown(f"""
<style>
  .stApp {{ background: {COLORS['bg']}; color: {COLORS['text']}; }}
  [data-testid="stSidebar"] {{ background: {COLORS['surface']}; }}
  [data-testid="stSidebar"] * {{ color: {COLORS['text']} !important; }}
  .kpi-card {{
    background: {COLORS['surface']}; border: 1px solid {COLORS['border']};
    border-radius: 12px; padding: 16px; text-align: center;
  }}
  .kpi-value {{ font-size: 2rem; font-weight: 800; margin: 4px 0; }}
  .kpi-label {{ font-size: 0.8rem; color: {COLORS['muted']}; font-weight: 600; }}
  .insight-card {{
    background: {COLORS['surface']}; border-left: 4px solid;
    border-radius: 0 12px 12px 0; padding: 16px 20px; margin-bottom: 16px;
  }}
  .insight-title {{ font-size: 1.05rem; font-weight: 700; margin-bottom: 10px; }}
  .insight-label {{ font-size: 0.78rem; font-weight: 700; opacity: 0.8; margin-bottom: 3px; }}
  .stTabs [data-baseweb="tab"] {{ color: {COLORS['muted']}; font-weight: 600; }}
  .stTabs [aria-selected="true"] {{ color: {COLORS['text']}; }}
  h1, h2, h3, h4 {{ color: {COLORS['text']} !important; }}
  p, li {{ color: {COLORS['text']} !important; }}
  .stCaption {{ color: {COLORS['muted']} !important; }}
  [data-testid="metric-container"] {{
    background: {COLORS['surface']}; border: 1px solid {COLORS['border']};
    border-radius: 10px;
  }}
  [data-testid="stMetricValue"] {{ color: {COLORS['rappi']} !important; }}
</style>
""", unsafe_allow_html=True)


# -- Streamlit compatibility helpers ------------------------------------
def safe_plotly_chart(fig, key: str = None):
    """Render Plotly chart -- hide modebar and support old/new Streamlit APIs."""
    if fig is None:
        return
    config = {
        "displayModeBar": False,
        "displaylogo": False,
        "responsive": True,
        "scrollZoom": False,
    }
    try:
        st.plotly_chart(fig, width="stretch", config=config, key=key)
        return
    except TypeError:
        pass
    try:
        st.plotly_chart(fig, use_container_width=True, config=config, key=key)
        return
    except TypeError:
        pass
    try:
        st.plotly_chart(fig, use_container_width=True, config=config)
        return
    except TypeError:
        pass
    try:
        st.plotly_chart(fig, config=config)
    except Exception as e:
        st.warning(f"Chart could not render: {e}")


def safe_dataframe(df, key: str = None):
    """Render DataFrame -- compatible with all Streamlit versions including 1.x."""
    if df is None or (hasattr(df, 'empty') and df.empty):
        st.info("No data to display.")
        return
    # Try each combination from most modern to most compatible,
    # dropping unsupported kwargs at each level.
    try:
        st.dataframe(df, width="stretch", hide_index=True, key=key)
        return
    except TypeError:
        pass
    try:
        st.dataframe(df, use_container_width=True, hide_index=True, key=key)
        return
    except TypeError:
        pass
    try:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return
    except TypeError:
        pass
    try:
        st.dataframe(df, use_container_width=True)
        return
    except TypeError:
        pass
    st.dataframe(df)


def safe_image(path: str, caption: str = ""):
    """Render image -- compatible with all Streamlit versions."""
    try:
        st.image(str(path), caption=caption, use_container_width=True)
    except TypeError:
        try:
            st.image(str(path), caption=caption, use_container_width=True)
        except Exception:
            st.caption(f"[Screenshot: {caption}]")


# -- Data loading -------------------------------------------------------
from normalize import normalize_dataset, get_summary_stats
from insights  import generate_insights
from charts import (
    price_grouped_bar, price_difference_vs_rappi_chart, avg_price_by_zone_chart,
    delivery_fee_heatmap, free_delivery_rate_bar, service_fee_boxplot, total_cost_comparison,
    eta_platform_bar, eta_by_zone, eta_by_city, eta_heatmap,
    promo_rate_bar, promo_heatmap
)

PROCESSED_DIR = BASE_DIR / "data" / "processed"


def _cache_data(fn):
    """Version-safe Streamlit cache — cache_data for Streamlit 1.18+."""
    try:
        return st.cache_data(ttl=300, show_spinner="Loading data...")(fn)
    except AttributeError:
        return fn


@_cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return normalize_dataset(df)


def plotly_dark(fig, title_suffix: str = ""):
    """Apply dark theme to Plotly figure."""
    if fig is None:
        return None
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text"], family="Inter, sans-serif", size=13),
        title_font=dict(size=16, color=COLORS["text"], family="Inter, sans-serif"),
        legend=dict(
            font=dict(color=COLORS["text"], size=12),
            bgcolor="rgba(30,41,59,0.7)",
            bordercolor=COLORS["border"],
            borderwidth=1,
            title_text="",
        ),
        xaxis=dict(
            color=COLORS["text"],
            gridcolor="rgba(51,65,85,0.5)",
            linecolor=COLORS["border"],
            tickfont=dict(color=COLORS["text"], size=12),
            title_font=dict(color=COLORS["muted"], size=12),
        ),
        yaxis=dict(
            color=COLORS["text"],
            gridcolor="rgba(51,65,85,0.5)",
            linecolor=COLORS["border"],
            tickfont=dict(color=COLORS["text"], size=12),
            title_font=dict(color=COLORS["muted"], size=12),
        ),
        margin=dict(t=50, b=40, l=40, r=20),
    )
    return fig


def no_data_msg(msg: str = "No hay datos suficientes para los filtros seleccionados."):
    st.info(msg)


def has_plot_data(df: pd.DataFrame, value_col: str = None, min_rows: int = 1) -> bool:
    if df is None or df.empty or len(df) < min_rows:
        return False
    if value_col is None:
        return True
    if value_col not in df.columns:
        return False
    vals = pd.to_numeric(df[value_col], errors="coerce")
    return vals.notna().sum() > 0


# -- Sidebar ------------------------------------------------------------
with st.sidebar:
    st.markdown("## Competitive Intelligence")
    st.markdown("**Rappi Mexico** -- Monitoring vs Uber Eats & DiDi Food")
    st.markdown("---")

    csv_files = sorted(PROCESSED_DIR.glob("competitive_prices_*.csv"), reverse=True)
    if not csv_files:
        st.error("No data files found.")
        st.info("Run: `python analysis/generate_demo_data.py`")
        st.stop()

    selected_file = st.selectbox(
        "Dataset",
        options=[str(f) for f in csv_files],
        format_func=lambda x: Path(x).stem,
    )

    df = load_data(selected_file)

    st.markdown("### Filters")
    all_cities    = sorted(df["city"].dropna().unique())
    all_zones     = sorted(df["zone_type"].dropna().unique())
    all_platforms = sorted(df["platform_label"].dropna().unique())
    all_products  = sorted(df["product_canonical"].dropna().unique())

    with st.expander(f"🏙️ City  ({len(all_cities)} available)", expanded=False):
        sel_cities = st.multiselect("", all_cities, default=all_cities)
    if len(sel_cities) < len(all_cities):
        st.caption(f"  ↳ {len(sel_cities)} of {len(all_cities)} cities")

    with st.expander(f"📍 Zone type  ({len(all_zones)} available)", expanded=False):
        sel_zones = st.multiselect("", all_zones, default=all_zones)
    if len(sel_zones) < len(all_zones):
        st.caption(f"  ↳ {len(sel_zones)} of {len(all_zones)} zones")

    with st.expander(f"🛵 Platform  ({len(all_platforms)} available)", expanded=False):
        sel_platforms = st.multiselect("", all_platforms, default=all_platforms)
    if len(sel_platforms) < len(all_platforms):
        st.caption(f"  ↳ {len(sel_platforms)} selected")

    with st.expander(f"🍔 Product  ({len(all_products)} available)", expanded=False):
        sel_products = st.multiselect("", all_products, default=all_products)
    if len(sel_products) < len(all_products):
        st.caption(f"  ↳ {len(sel_products)} of {len(all_products)} products")

    fdf = df[
        df["city"].isin(sel_cities) &
        df["zone_type"].isin(sel_zones) &
        df["platform_label"].isin(sel_platforms) &
        df["product_canonical"].isin(sel_products) &
        df["has_price"]
    ]

    st.markdown("---")
    st.caption(f"Total rows: {len(df):,}")
    st.caption(f"With price: {len(fdf):,}")
    if "scraped_at" in df.columns and df["scraped_at"].notna().any():
        try:
            last = pd.to_datetime(df["scraped_at"], errors="coerce").max()
            if pd.notna(last):
                st.caption(f"Last scrape: {last.strftime('%d %b %Y %H:%M')}")
        except Exception:
            pass


# -- TABS ---------------------------------------------------------------
tab_overview, tab_price, tab_fees, tab_eta, tab_promo, tab_insights, tab_evidence = st.tabs([
    "Overview",
    "Pricing",
    "Fees",
    "ETA",
    "Promotions",
    "Top 5 Insights",
    "Evidence",
])


# ========================================================================
# TAB 1: OVERVIEW
# ========================================================================
with tab_overview:
    st.markdown("### Overview -- Market Summary")
    st.caption("McDonald's Mexico * Rappi vs Uber Eats vs DiDi Food")

    if fdf.empty:
        no_data_msg()
    else:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Addresses",    fdf["address_id"].nunique())
        c2.metric("Cities",       fdf["city"].nunique())
        c3.metric("Platforms",    fdf["platform_label"].nunique())
        c4.metric("Products",     fdf["product_canonical"].nunique())
        c5.metric("Observations", f"{len(fdf):,}")
        avg_r = fdf[fdf["platform"]=="rappi"]["product_price"].mean()
        avg_u = fdf[fdf["platform"]=="uber"]["product_price"].mean()
        if avg_u and avg_u > 0:
            delta_pct = (avg_r - avg_u) / avg_u * 100
            c6.metric("Rappi vs Uber (price)", f"${avg_r:.0f}", f"{delta_pct:+.1f}%")
        else:
            c6.metric("Rappi avg price", f"${avg_r:.0f}" if avg_r else "N/A")

        # -- Data Quality signal ----------------------------------------
        st.markdown("---")
        st.markdown("#### Data Quality")
        dq1, dq2, dq3, dq4 = st.columns(4)
        total_rows = len(df[
            df["city"].isin(sel_cities) &
            df["zone_type"].isin(sel_zones) &
            df["platform_label"].isin(sel_platforms) &
            df["product_canonical"].isin(sel_products)
        ])
        success_rows = len(fdf)
        with_eta = fdf["eta_midpoint"].notna().sum()
        blocked = total_rows - success_rows
        dq1.metric("✅ Valid prices",  f"{success_rows:,}",   f"{success_rows/max(total_rows,1)*100:.0f}% of total")
        dq2.metric("⏱ With ETA",      f"{with_eta:,}",       f"{with_eta/max(success_rows,1)*100:.0f}% of priced")
        dq3.metric("❌ Missing/blocked", f"{blocked:,}",      f"{blocked/max(total_rows,1)*100:.0f}% of total")
        dq4.metric("📍 Addresses",     fdf["address_id"].nunique())
        st.markdown("---")

        if PLOTLY_OK:
            fig = price_grouped_bar(fdf, "Avg Price by Product & Platform (MXN)")
            if fig is not None:
                safe_plotly_chart(fig, key="ov_price")
            else:
                st.info("No price data available for the selected filters.")

            fig2 = eta_platform_bar(fdf, "Avg ETA by Platform (minutes)")
            if fig2 is not None:
                safe_plotly_chart(fig2, key="ov_eta")
            else:
                st.info("No ETA data available for the selected filters.")
        else:
            st.info("Install plotly for charts.")

        st.markdown("#### Platform Summary")
        summary_tbl = fdf.groupby("platform_label").agg(
            product_price   = ("product_price",    "mean"),
            delivery_fee    = ("delivery_fee",     "mean"),
            service_fee     = ("service_fee",      "mean"),
            eta_min         = ("eta_min",          "mean"),
            eta_max         = ("eta_max",          "mean"),
            promo_rate      = ("discount_visible", "mean"),
            n_obs           = ("product_price",    "count"),
        ).round(2).reset_index()
        summary_tbl["promo_rate"] = (summary_tbl["promo_rate"] * 100).round(1).astype(str) + "%"
        summary_tbl.columns = [
            "Platform","Price ($)","Delivery ($)","Service ($)",
            "ETA min","ETA max","Promo rate","N obs"
        ]
        safe_dataframe(summary_tbl, key="ov_tbl")


# ========================================================================
# TAB 2: PRICING
# ========================================================================
with tab_price:
    st.markdown("### Pricing Analysis")

    if fdf.empty or not PLOTLY_OK:
        no_data_msg()
    else:
        fig = price_grouped_bar(fdf, "Avg Product Price (MXN)")
        if fig is not None:
            safe_plotly_chart(fig, key="pr_main")

        fig2 = price_difference_vs_rappi_chart(fdf, "Price Difference vs Rappi (%)")
        if fig2 is not None:
            safe_plotly_chart(fig2, key="pr_diff")
        else:
            st.info("No baseline (Rappi) data to compute price difference.")

        fig3 = avg_price_by_zone_chart(fdf, "Avg Price by Zone Type (MXN)")
        if fig3 is not None:
            safe_plotly_chart(fig3, key="pr_zone")

        fig4 = plotly_dark(px.box(
            fdf, x="platform_label", y="product_price",
            color="platform_label", color_discrete_map=PLATFORM_COLORS,
            title="Price Distribution by Platform",
            points="outliers",
        ))
        if fig4:
            fig4.update_yaxes(tickprefix="$", tickformat=",.0f", rangemode="tozero")
        safe_plotly_chart(fig4, key="pr_box")


# ========================================================================
# TAB 3: FEES
# ========================================================================
with tab_fees:
    st.markdown("### Fee Analysis")

    if fdf.empty or not PLOTLY_OK:
        no_data_msg()
    else:
        fig = delivery_fee_heatmap(fdf, "Delivery Fee (MXN) by Zone & Platform")
        if fig is not None:
            safe_plotly_chart(fig, key="fee_heat")
        else:
            st.info("Not enough data to render delivery fee heatmap.")

        fig2 = free_delivery_rate_bar(fdf, "Free Delivery Rate (%)")
        if fig2 is not None:
            safe_plotly_chart(fig2, key="fee_free")
        else:
            st.info("Free delivery rate is similarly distributed across platforms or no fee data is available.")

        fig3 = service_fee_boxplot(fdf, "Service Fee as % of Product Price")
        if fig3 is not None:
            safe_plotly_chart(fig3, key="svc_box")
        else:
            st.info("Not enough service fee observations for the current filters.")

        fig4 = total_cost_comparison(fdf, "Estimated Total Cost to User — Product + Fees (MXN)")
        if fig4 is not None:
            safe_plotly_chart(fig4, key="fee_total")
            st.caption("Total = product price + delivery fee + service fee − discounts applied")
        else:
            st.info("Not enough valid total-cost observations for the current filters.")


# ========================================================================
# TAB 4: ETA
# ========================================================================
with tab_eta:
    st.markdown("### Estimated Delivery Time (ETA)")

    eta_df = fdf[fdf["eta_midpoint"].notna()]
    if eta_df.empty:
        st.info("No ETA data available for the selected filters. "
                "ETA is captured during live scraping -- demo data includes simulated values.")
    elif not PLOTLY_OK:
        no_data_msg("Install plotly to view ETA charts.")
    else:
        fig = eta_by_zone(eta_df, "Avg Delivery Time by Zone (minutes)")
        if fig is not None:
            safe_plotly_chart(fig, key="eta_zone")
        else:
            st.info("Not enough ETA observations per zone for a reliable comparison (min 3 per group required).")

        city_col = "city_short" if "city_short" in eta_df.columns else "city"
        fig2 = eta_by_city(eta_df, city_col=city_col, title="Avg Delivery Time by City (minutes)")
        if fig2 is not None:
            safe_plotly_chart(fig2, key="eta_city")
        else:
            st.info("Not enough ETA data per city for a reliable comparison.")

        fig3 = eta_heatmap(eta_df, "ETA Heatmap (minutes) by Zone & Platform")
        if fig3 is not None:
            safe_plotly_chart(fig3, key="eta_heat")
        else:
            st.info("Not enough data for ETA heatmap with current filters.")


# ========================================================================
# TAB 5: PROMOTIONS
# ========================================================================
with tab_promo:
    st.markdown("### Promotional Strategy")

    if fdf.empty or not PLOTLY_OK:
        no_data_msg()
    else:
        fig = promo_rate_bar(fdf, "Promotion Visibility Rate (%)")
        if fig is not None:
            safe_plotly_chart(fig, key="promo_bar")
        else:
            st.info("Not enough promotion data for the selected filters.")

        fig2 = promo_heatmap(fdf, "Promo Rate (%) by Zone & Platform")
        if fig2 is not None:
            safe_plotly_chart(fig2, key="promo_heat")
        else:
            st.info("Not enough data for promotion heatmap.")

        promo_df = fdf[fdf["discount_visible"] == True]
        if len(promo_df) > 0:
            labels = promo_df.groupby(["platform_label","discount_label"]).size().reset_index(name="count")
            labels = labels[labels["discount_label"].notna() & (labels["discount_label"] != "")]
            if len(labels) > 0:
                fig3 = plotly_dark(px.bar(
                    labels.sort_values("count", ascending=False).head(20),
                    x="count", y="discount_label", color="platform_label",
                    color_discrete_map=PLATFORM_COLORS,
                    orientation="h",
                    title="Most Frequent Promotion Types",
                ))
                safe_plotly_chart(fig3, key="promo_labels")
        else:
            st.info("No promotional observations in the current filtered dataset.")


# ========================================================================
# TAB 6: TOP 5 INSIGHTS
# ========================================================================
with tab_insights:
    st.markdown("### Top 5 Competitive Insights")
    st.caption("Actionable findings for Strategy & Pricing teams")

    if fdf.empty or len(fdf) < 10:
        st.warning("Not enough data to generate insights. "
                   "Run: `python analysis/generate_demo_data.py` first.")
    else:
        try:
            insights = generate_insights(fdf)
        except Exception as e:
            st.error(f"Insight generation failed: {e}")
            insights = []

        if not insights:
            st.info("No insights generated for the current data.")
        else:
            sev_colors = {"high": COLORS["danger"], "medium": COLORS["warning"], "low": COLORS["success"]}
            sev_labels = {"high": "High", "medium": "Medium", "low": "Low"}

            for ins in insights:
                sev   = ins.get("severity", "medium")
                color = sev_colors.get(sev, COLORS["warning"])

                st.markdown(f"""
<div class="insight-card" style="border-color:{color}; margin-bottom:20px;">
  <div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
    <span style="font-size:1.3rem; font-weight:800; color:{color};">#{ins['id']}</span>
    <span style="font-size:0.78rem; font-weight:700; background:#334155;
                 padding:3px 10px; border-radius:20px; color:#CBD5E1;">{ins['category']}</span>
    <span style="font-size:0.78rem; font-weight:700; background:{color}20;
                 color:{color}; padding:3px 10px; border-radius:20px;">
      Priority: {sev_labels[sev]}</span>
  </div>
  <div class="insight-title">{ins['title']}</div>
  <div class="insight-label" style="color:{COLORS['muted']};">FINDING</div>
  <div style="margin-bottom:10px; font-size:0.9rem;">{ins['finding']}</div>
  <div class="insight-label" style="color:{COLORS['muted']};">IMPACT</div>
  <div style="margin-bottom:10px; font-size:0.9rem;">{ins['impact']}</div>
  <div class="insight-label" style="color:{COLORS['muted']};">RECOMMENDATION</div>
  <div style="font-size:0.9rem; font-weight:500;">{ins['recommendation']}</div>
</div>""", unsafe_allow_html=True)

                data = ins.get("data")
                if isinstance(data, pd.DataFrame) and not data.empty:
                    with st.expander(f"View supporting data ({len(data)} rows)"):
                        safe_dataframe(data, key=f"ins_data_{ins['id']}")


# ========================================================================
# TAB 7: EVIDENCE
# ========================================================================
with tab_evidence:
    st.markdown("### Evidence & Raw Data")

    SCREENSHOTS_DIR = BASE_DIR / "data" / "screenshots"
    screenshots = list(SCREENSHOTS_DIR.glob("*.png")) if SCREENSHOTS_DIR.exists() else []

    # -- Screenshot filters ---------------------------------------------
    if screenshots:
        st.markdown(f"#### Screenshots ({len(screenshots)} captured)")
        plat_filter = st.selectbox(
            "Filter by platform", ["All"] + ["rappi","uber","didi"], key="ev_plat"
        )
        filtered_shots = [
            s for s in screenshots
            if plat_filter == "All" or plat_filter in s.name
        ]
        if not filtered_shots:
            st.info("No screenshots match the filter.")
        else:
            cols = st.columns(3)
            for i, shot in enumerate(filtered_shots[:12]):
                with cols[i % 3]:
                    safe_image(str(shot), caption=shot.stem)
    else:
        st.info("No screenshots available. They are auto-captured during live scraping.")

    st.markdown("---")

    # -- Raw data table with filters (self-contained, no sidebar deps) ----
    st.markdown("#### Raw Observations")

    _ev_platforms = sorted(df["platform_label"].dropna().unique().tolist())
    _ev_cities    = sorted(df["city"].dropna().unique().tolist())
    _ev_statuses  = sorted(df["status"].dropna().unique().tolist()) if "status" in df.columns else []

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        ev_plat   = st.multiselect("Platform", _ev_platforms,
                                   default=_ev_platforms, key="ev_r_plat")
    with col_f2:
        ev_city   = st.multiselect("City",     _ev_cities,
                                   default=_ev_cities, key="ev_r_city")
    with col_f3:
        ev_status = st.multiselect("Status", _ev_statuses,
                                   default=_ev_statuses, key="ev_r_status")

    ev_df = df.copy()
    if ev_plat:
        ev_df = ev_df[ev_df["platform_label"].isin(ev_plat)]
    if ev_city:
        ev_df = ev_df[ev_df["city"].isin(ev_city)]
    if ev_status and "status" in ev_df.columns:
        ev_df = ev_df[ev_df["status"].isin(ev_status)]

    display_cols = [c for c in [
        "platform_label","city","address_id","zone_type","product_canonical",
        "product_price","delivery_fee","service_fee","eta_min","eta_max",
        "discount_visible","discount_label","status","error_message","scraped_at"
    ] if c in ev_df.columns]

    st.caption(f"Showing {min(100, len(ev_df))} of {len(ev_df):,} rows")
    safe_dataframe(ev_df[display_cols].head(100), key="ev_raw")

    if not ev_df.empty:
        st.download_button(
            "Download filtered CSV",
            ev_df[display_cols].to_csv(index=False),
            file_name="competitive_intelligence_export.csv",
            mime="text/csv",
        )
