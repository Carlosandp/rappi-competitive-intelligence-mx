"""
normalize.py — Clean and normalize raw scraped data.

Handles:
- Price outlier detection and flagging
- ETA normalization to midpoint
- Missing fee imputation rules
- Zone type standardization
- Platform name canonicalization
"""
from __future__ import annotations
from typing import Optional, Union

import numpy as np
import pandas as pd


PLATFORM_LABELS = {
    "rappi": "Rappi",
    "uber":  "Uber Eats",
    "didi":  "DiDi Food",
}

ZONE_ORDER = ["premium", "residential_premium", "commercial", "residential_medium", "peripheral"]

PRODUCT_ORDER = [
    "Big Mac",
    "McTrio Big Mac Mediano",
    "McNuggets 10 piezas",
    "Papas a la Francesa Medianas",
]


def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full normalization pipeline.
    Input:  raw CSV from scraping (or synthetic backup)
    Output: clean DataFrame ready for analysis and dashboard
    """
    df = df.copy()

    # -- 1. Column typing --------------------------------------------------
    numeric_cols = [
        "product_price", "delivery_fee", "service_fee",
        "discount_amount", "eta_min", "eta_max",
        "subtotal", "final_total",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Bool parsing -- preserve NaN for unknown values (do NOT default to False)
    _TRUE_VALS  = {"true", "1", "yes", "si", "si"}
    _FALSE_VALS = {"false", "0", "no"}
    def _parse_bool(x):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return np.nan
        s = str(x).strip().lower()
        if s in _TRUE_VALS:  return True
        if s in _FALSE_VALS: return False
        return np.nan

    bool_cols = ["store_available", "discount_visible"]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].apply(_parse_bool)

    if "scraped_at" in df.columns:
        df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")

    # -- 2. Platform label --------------------------------------------------
    df["platform_label"] = df["platform"].map(PLATFORM_LABELS).fillna(df["platform"])

    # -- 3. ETA midpoint ---------------------------------------------------
    df["eta_midpoint"] = df.apply(
        lambda r: (r["eta_min"] + r["eta_max"]) / 2
        if pd.notna(r.get("eta_min")) and pd.notna(r.get("eta_max"))
        else r.get("eta_min") or r.get("eta_max"),
        axis=1,
    )

    # -- 4. Effective total ------------------------------------------------
    df["effective_total"] = df.apply(_compute_effective_total, axis=1)

    # -- 5. Price vs Rappi delta -------------------------------------------
    rappi_prices = (
        df[df["platform"] == "rappi"]
        .groupby(["address_id", "product_canonical"])["product_price"]
        .mean()
        .reset_index()
        .rename(columns={"product_price": "rappi_price"})
    )
    df = df.merge(rappi_prices, on=["address_id", "product_canonical"], how="left")
    df["price_vs_rappi_abs"]  = df["product_price"] - df["rappi_price"]
    # Guard against division by zero or missing baseline
    safe_rappi = df["rappi_price"].replace(0, np.nan)
    df["price_vs_rappi_pct"] = np.where(
        safe_rappi.notna() & df["product_price"].notna(),
        (df["product_price"] - safe_rappi) / safe_rappi * 100,
        np.nan,
    ).round(2)

    # -- 6. Zone type ordering ----------------------------------------------
    df["zone_type_order"] = df["zone_type"].map(
        {z: i for i, z in enumerate(ZONE_ORDER)}
    ).fillna(99)

    # -- 7. Success filter flag ---------------------------------------------
    df["is_success"] = df["status"].isin(["success", "partial"])
    df["has_price"]  = df["product_price"].notna() & df["is_success"]

    # -- 8. Delivery fee 0 = free -------------------------------------------
    df["delivery_fee_display"] = df["delivery_fee"].apply(
        lambda v: "Gratis" if v == 0 else (f"${v:.2f}" if pd.notna(v) else "N/D")
    )

    # -- 9. Outlier flags ---------------------------------------------------
    for metric in ["product_price", "delivery_fee", "eta_midpoint"]:
        if metric in df.columns:
            grp = df.groupby(["platform", "product_canonical"])[metric]
            df[f"{metric}_zscore"] = grp.transform(
                lambda x: (x - x.mean()) / (x.std() + 1e-9)
            )
            df[f"{metric}_outlier"] = df[f"{metric}_zscore"].abs() > 2.5

    # -- 10. City short name -----------------------------------------------
    city_map = {
        "Ciudad de México": "CDMX",
        "Guadalajara":      "GDL",
        "Monterrey":        "MTY",
    }
    df["city_short"] = df["city"].map(city_map).fillna(df["city"])

    return df


def _compute_effective_total(row):  # -> Optional[float]
    """Best estimate of what user pays."""
    if pd.notna(row.get("final_total")):
        return row["final_total"]
    total = 0.0
    has_any = False
    if pd.notna(row.get("product_price")):
        total   += row["product_price"]
        has_any  = True
    if pd.notna(row.get("delivery_fee")):
        total += row["delivery_fee"]
    if pd.notna(row.get("service_fee")):
        total += row["service_fee"]
    if pd.notna(row.get("discount_amount")):
        total -= row["discount_amount"]
    return round(total, 2) if has_any else None


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Return high-level summary statistics for the dataset."""
    success_df = df[df["has_price"]]
    return {
        "total_observations":  len(df),
        "successful_prices":   len(success_df),
        "success_rate":        round(len(success_df) / max(len(df), 1), 3),
        "platforms":           df["platform_label"].nunique(),
        "addresses":           df["address_id"].nunique(),
        "cities":              df["city"].nunique(),
        "products":            df["product_canonical"].nunique(),
        "avg_price_rappi":     success_df[success_df["platform"]=="rappi"]["product_price"].mean(),
        "avg_price_uber":      success_df[success_df["platform"]=="uber"]["product_price"].mean(),
        "avg_price_didi":      success_df[success_df["platform"]=="didi"]["product_price"].mean(),
        "avg_eta_rappi":       success_df[success_df["platform"]=="rappi"]["eta_midpoint"].mean(),
        "avg_eta_uber":        success_df[success_df["platform"]=="uber"]["eta_midpoint"].mean(),
        "avg_eta_didi":        success_df[success_df["platform"]=="didi"]["eta_midpoint"].mean(),
        "avg_delivery_fee_rappi": success_df[success_df["platform"]=="rappi"]["delivery_fee"].mean(),
        "avg_delivery_fee_uber":  success_df[success_df["platform"]=="uber"]["delivery_fee"].mean(),
        "avg_delivery_fee_didi":  success_df[success_df["platform"]=="didi"]["delivery_fee"].mean(),
        "promo_rate_rappi":    df[df["platform"]=="rappi"]["discount_visible"].mean(),
        "promo_rate_uber":     df[df["platform"]=="uber"]["discount_visible"].mean(),
        "promo_rate_didi":     df[df["platform"]=="didi"]["discount_visible"].mean(),
    }
