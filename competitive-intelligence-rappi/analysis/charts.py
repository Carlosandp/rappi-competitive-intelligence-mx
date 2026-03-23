"""
Reusable Plotly chart factories for the competitive intelligence dashboard.
Focused on dark-theme readability and safe rendering in Streamlit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

PLATFORM_COLORS = {
    "Rappi": "#FF441F",
    "Uber Eats": "#06C167",
    "DiDi Food": "#FF6B00",
}

DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#F8FAFC", family="Inter, sans-serif", size=13),
    title_font=dict(size=18, color="#F8FAFC", family="Inter, sans-serif"),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.08,
        xanchor="right",
        x=1,
        font=dict(color="#F8FAFC", size=12),
        bgcolor="rgba(30,41,59,0.65)",
        bordercolor="#334155",
        borderwidth=1,
        title_text="",
    ),
    margin=dict(l=60, r=30, t=90, b=90),
    height=430,
    uniformtext=dict(minsize=10, mode="hide"),
)


def _apply_dark(fig):
    if fig is None:
        return None
    fig.update_layout(**DARK_LAYOUT)
    fig.update_xaxes(
        color="#CBD5E1",
        gridcolor="rgba(148,163,184,0.16)",
        linecolor="#334155",
        tickfont=dict(color="#F8FAFC", size=12),
        title_font=dict(color="#CBD5E1", size=12),
        automargin=True,
    )
    fig.update_yaxes(
        color="#CBD5E1",
        gridcolor="rgba(148,163,184,0.16)",
        linecolor="#334155",
        tickfont=dict(color="#F8FAFC", size=12),
        title_font=dict(color="#CBD5E1", size=12),
        automargin=True,
    )
    return fig


def _ymax(vals: pd.Series, min_floor: float = 10.0, pad: float = 0.20) -> float:
    vals = pd.to_numeric(vals, errors="coerce").dropna()
    if vals.empty:
        return min_floor
    vmax = float(vals.max())
    return max(min_floor, vmax * (1 + pad))


def _bar(fig, yvals: pd.Series, tickprefix: str = "", ticksuffix: str = ""):
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_yaxes(range=[0, _ymax(yvals)], tickformat=",.0f",
                     tickprefix=tickprefix, ticksuffix=ticksuffix)
    # Extra bottom margin so x-axis labels don't get clipped when automargin is on
    fig.update_layout(margin=dict(b=100))
    return _apply_dark(fig)


def categorical_heatmap(pivot: pd.DataFrame, title: str, colorbar_title: str, colorscale=None, text_format: str = ".1f"):
    if not PLOTLY_AVAILABLE or pivot is None or pivot.empty:
        return None
    colorscale = colorscale or [[0, "#1E293B"], [0.5, "#3B82F6"], [1, "#22C55E"]]
    text = [[format(v, text_format) if pd.notna(v) else "" for v in row] for row in pivot.values]
    height = max(340, 70 * len(pivot.index) + 140)
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale=colorscale,
            text=text,
            texttemplate="%{text}",
            textfont={"color": "#F8FAFC", "size": 13},
            colorbar={
                "title": {"text": colorbar_title, "font": {"color": "#F8FAFC"}},
                "tickfont": {"color": "#F8FAFC"},
                "len": 0.9,
                "thickness": 16,
                "x": 1.02,
            },
            hovertemplate="Zone: %{y}<br>Platform: %{x}<br>Value: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Platform",
        yaxis_title="Zone Type",
        height=height,
        margin=dict(l=90, r=80, t=90, b=60),
    )
    fig.update_xaxes(type="category")
    fig.update_yaxes(type="category")
    return _apply_dark(fig)


def price_grouped_bar(df: pd.DataFrame, title: str = "Avg Price by Product & Platform (MXN)"):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    grp = df.groupby(["platform_label", "product_canonical"], as_index=False)["product_price"].mean()
    if grp.empty:
        return None
    fig = px.bar(
        grp,
        x="product_canonical",
        y="product_price",
        color="platform_label",
        barmode="group",
        color_discrete_map=PLATFORM_COLORS,
        title=title,
        labels={"product_price": "Price (MXN)", "product_canonical": "Product", "platform_label": "Platform"},
        text=grp["product_price"].apply(lambda v: f"${v:.0f}"),
    )
    fig.update_xaxes(tickangle=-22)
    return _bar(fig, grp["product_price"], tickprefix="$")


def price_difference_vs_rappi_chart(df: pd.DataFrame, title: str = "Price Difference vs Rappi (%)"):
    if not PLOTLY_AVAILABLE or df.empty or "price_vs_rappi_pct" not in df.columns:
        return None
    grp = df[(df["platform_label"] != "Rappi") & df["price_vs_rappi_pct"].notna()].groupby(["platform_label", "product_canonical"], as_index=False)["price_vs_rappi_pct"].mean()
    if grp.empty:
        return None
    fig = px.bar(
        grp, x="product_canonical", y="price_vs_rappi_pct",
        color="platform_label", barmode="group",
        color_discrete_map=PLATFORM_COLORS,
        title=title,
        labels={"price_vs_rappi_pct": "% vs Rappi", "product_canonical": "Product", "platform_label": "Platform"},
        text=grp["price_vs_rappi_pct"].apply(lambda v: f"{v:.1f}%"),
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#CBD5E1", opacity=0.5)
    fig.update_xaxes(tickangle=-22)
    absmax = max(5.0, float(pd.to_numeric(grp["price_vs_rappi_pct"], errors="coerce").abs().max()) * 1.25)
    fig.update_traces(textposition="outside", cliponaxis=False)
    # Symmetric axis so negative bars (competitors cheaper than Rappi) are visible
    fig.update_yaxes(range=[-absmax, absmax], tickformat=",.1f", ticksuffix="%")
    return _apply_dark(fig)


def avg_price_by_zone_chart(df: pd.DataFrame, title: str = "Avg Price by Zone Type (MXN)"):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    zone_price = df.groupby(["platform_label", "zone_type"], as_index=False)["product_price"].mean()
    if zone_price.empty:
        return None
    unique_zones = zone_price["zone_type"].dropna().unique().tolist()
    if len(unique_zones) == 1:
        grp = zone_price.groupby("platform_label", as_index=False)["product_price"].mean()
        fig = px.bar(
            grp,
            x="platform_label",
            y="product_price",
            color="platform_label",
            color_discrete_map=PLATFORM_COLORS,
            title=f"Avg Price in Selected Zone ({unique_zones[0]}) (MXN)",
            labels={"product_price": "Price (MXN)", "platform_label": "Platform"},
            text=grp["product_price"].apply(lambda v: f"${v:.0f}"),
        )
        return _bar(fig, grp["product_price"], tickprefix="$")
    fig = px.bar(
        zone_price,
        x="zone_type",
        y="product_price",
        color="platform_label",
        barmode="group",
        color_discrete_map=PLATFORM_COLORS,
        title=title,
        labels={"product_price": "Price (MXN)", "zone_type": "Zone", "platform_label": "Platform"},
        text=zone_price["product_price"].apply(lambda v: f"${v:.0f}"),
    )
    return _bar(fig, zone_price["product_price"], tickprefix="$")


def delivery_fee_heatmap(df: pd.DataFrame, title: str = "Delivery Fee (MXN) by Zone & Platform"):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    grp = df[df["delivery_fee"].notna()].groupby(["zone_type", "platform_label"], as_index=False)["delivery_fee"].mean()
    if grp.empty:
        return None
    pivot = grp.pivot(index="zone_type", columns="platform_label", values="delivery_fee").round(1)
    return categorical_heatmap(pivot, title, "Fee (MXN)", colorscale=[[0, "#1E293B"], [0.5, "#F59E0B"], [1, "#EF4444"]], text_format=".0f")


def free_delivery_rate_bar(df: pd.DataFrame, title: str = "Free Delivery Rate (%)"):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    grp = df[df["delivery_fee"].notna()].groupby("platform_label", as_index=False)["delivery_fee"].apply(lambda s: (s == 0).mean() * 100)
    if isinstance(grp, pd.Series):
        grp = grp.reset_index(name="rate_pct")
    else:
        grp.columns = ["platform_label", "rate_pct"]
    if grp.empty:
        return None
    fig = px.bar(
        grp, x="platform_label", y="rate_pct", color="platform_label",
        color_discrete_map=PLATFORM_COLORS, title=title,
        labels={"rate_pct": "Free Delivery %", "platform_label": "Platform"},
        text=grp["rate_pct"].apply(lambda v: f"{v:.0f}%"),
    )
    return _bar(fig, grp["rate_pct"], ticksuffix="%")


def service_fee_boxplot(df: pd.DataFrame, title: str = "Service Fee as % of Product Price"):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    svc = df[df["service_fee"].notna() & (df["service_fee"] > 0) & df["product_price"].notna()].copy()
    if len(svc) < 3:
        return None
    svc["svc_pct"] = (svc["service_fee"] / svc["product_price"] * 100).round(1)
    fig = px.box(
        svc, x="platform_label", y="svc_pct", color="platform_label",
        color_discrete_map=PLATFORM_COLORS, title=title,
        labels={"svc_pct": "Service Fee (%)", "platform_label": "Platform"}, points="all"
    )
    fig.update_yaxes(ticksuffix="%", rangemode="tozero")
    return _apply_dark(fig)


def total_cost_comparison(df: pd.DataFrame, title: str = "Estimated Total Cost to User — Product + Fees (MXN)"):
    if not PLOTLY_AVAILABLE or df.empty or "effective_total" not in df.columns:
        return None
    fdf = df[df["effective_total"].notna() & (df["effective_total"] > 20)]
    if fdf.empty:
        return None
    grp = fdf.groupby(["platform_label", "product_canonical"], as_index=False)["effective_total"].mean()
    fig = px.bar(
        grp, x="product_canonical", y="effective_total", color="platform_label",
        barmode="group", color_discrete_map=PLATFORM_COLORS, title=title,
        labels={"effective_total": "Total (MXN)", "product_canonical": "Product", "platform_label": "Platform"},
        text=grp["effective_total"].apply(lambda v: f"${v:.0f}"),
    )
    fig.update_xaxes(tickangle=-22)
    return _bar(fig, grp["effective_total"], tickprefix="$")


def eta_platform_bar(df: pd.DataFrame, title: str = "Avg ETA by Platform (minutes)"):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    grp = df[df["eta_midpoint"].notna()].groupby("platform_label", as_index=False)["eta_midpoint"].mean()
    if grp.empty:
        return None
    fig = px.bar(
        grp, x="platform_label", y="eta_midpoint", color="platform_label",
        color_discrete_map=PLATFORM_COLORS, title=title,
        labels={"eta_midpoint": "ETA (min)", "platform_label": "Platform"},
        text=grp["eta_midpoint"].apply(lambda v: f"{v:.0f} min"),
    )
    return _bar(fig, grp["eta_midpoint"], ticksuffix=" min")


def eta_by_zone(df: pd.DataFrame, title: str = "Avg Delivery Time by Zone (minutes)", min_n: int = 3):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    grp = df[df["eta_midpoint"].notna()].groupby(["platform_label", "zone_type"], as_index=False).agg(
        eta_mean=("eta_midpoint", "mean"),
        n_obs=("eta_midpoint", "count"),
    )
    grp = grp[grp["n_obs"] >= min_n]
    if grp.empty:
        return None
    fig = px.bar(
        grp, x="zone_type", y="eta_mean", color="platform_label", barmode="group",
        color_discrete_map=PLATFORM_COLORS, title=title,
        labels={"eta_mean": "ETA (min)", "zone_type": "Zone", "platform_label": "Platform"},
        text=grp["eta_mean"].apply(lambda v: f"{v:.0f} min"), hover_data=["n_obs"],
    )
    return _bar(fig, grp["eta_mean"], ticksuffix=" min")


def eta_by_city(df: pd.DataFrame, city_col: str = "city", title: str = "Avg Delivery Time by City (minutes)", min_n: int = 3):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    grp = df[df["eta_midpoint"].notna()].groupby(["platform_label", city_col], as_index=False).agg(
        eta_mean=("eta_midpoint", "mean"),
        n_obs=("eta_midpoint", "count"),
    )
    grp = grp[grp["n_obs"] >= min_n]
    if grp.empty:
        return None
    fig = px.bar(
        grp, x=city_col, y="eta_mean", color="platform_label", barmode="group",
        color_discrete_map=PLATFORM_COLORS, title=title,
        labels={"eta_mean": "ETA (min)", city_col: "City", "platform_label": "Platform"},
        text=grp["eta_mean"].apply(lambda v: f"{v:.0f} min"), hover_data=["n_obs"],
    )
    return _bar(fig, grp["eta_mean"], ticksuffix=" min")


def eta_heatmap(df: pd.DataFrame, title: str = "ETA Heatmap (minutes) by Zone & Platform", min_n: int = 3):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    grp = df[df["eta_midpoint"].notna()].groupby(["zone_type", "platform_label"], as_index=False).agg(
        eta_mean=("eta_midpoint", "mean"),
        n_obs=("eta_midpoint", "count"),
    )
    grp = grp[grp["n_obs"] >= min_n]
    if grp.empty:
        return None
    pivot = grp.pivot(index="zone_type", columns="platform_label", values="eta_mean").round(1)
    return categorical_heatmap(pivot, title, "ETA (min)", colorscale=[[0, "#22C55E"], [0.5, "#F59E0B"], [1, "#EF4444"]], text_format=".0f")


def promo_rate_bar(df: pd.DataFrame, title: str = "Promotion Visibility Rate (%)"):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    promo = df[df["discount_visible"].notna()].copy()
    if promo.empty:
        return None
    grp = promo.groupby("platform_label", as_index=False)["discount_visible"].mean()
    grp["rate_pct"] = (grp["discount_visible"] * 100).round(1)
    fig = px.bar(
        grp, x="platform_label", y="rate_pct", color="platform_label",
        color_discrete_map=PLATFORM_COLORS, title=title,
        labels={"rate_pct": "% Observations w/ Promo", "platform_label": "Platform"},
        text=grp["rate_pct"].apply(lambda v: f"{v:.0f}%"),
    )
    return _bar(fig, grp["rate_pct"], ticksuffix="%")


def promo_heatmap(df: pd.DataFrame, title: str = "Promo Rate (%) by Zone & Platform"):
    if not PLOTLY_AVAILABLE or df.empty:
        return None
    promo = df[df["discount_visible"].notna()].copy()
    if promo.empty:
        return None
    grp = promo.groupby(["zone_type", "platform_label"], as_index=False)["discount_visible"].mean()
    grp["rate_pct"] = (grp["discount_visible"] * 100).round(1)
    pivot = grp.pivot(index="zone_type", columns="platform_label", values="rate_pct")
    return categorical_heatmap(pivot, title, "Promo %", colorscale=[[0, "#1E293B"], [0.5, "#3B82F6"], [1, "#22C55E"]], text_format=".0f")
