"""
generate_demo_data.py — Creates a realistic synthetic dataset for demo backup.

Rationale: The brief explicitly recommends having pre-scraped data as backup.
This generator creates statistically realistic pricing data based on:
- Known McDonald's price ranges in Mexico (MXN 89-250 for target items)
- Typical delivery fee structures per platform (Rappi: ~$25-49, Uber: ~$15-39, DiDi: ~$10-35)
- Service fee structures (Rappi: ~5-10%, Uber: ~15%, DiDi: ~8-12%)
- ETA ranges typical for each zone type
- Realistic promotional patterns

Output: data/processed/competitive_prices_demo.csv
"""
from __future__ import annotations

import csv
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "scrapers"))

from config import OUTPUT_COLUMNS, PROCESSED_DIR, INPUT_DIR

random.seed(42)
np.random.seed(42)

# -- Price anchors (MXN, realistic 2024 Mexico prices) -------------------
PRODUCT_PRICES = {
    "Big Mac": {
        "rappi": {"mean": 105, "std": 8,  "min": 89,  "max": 125},
        "uber":  {"mean": 99,  "std": 7,  "min": 85,  "max": 119},
        "didi":  {"mean": 102, "std": 9,  "min": 87,  "max": 120},
    },
    "McTrio Big Mac Mediano": {
        "rappi": {"mean": 185, "std": 12, "min": 159, "max": 215},
        "uber":  {"mean": 179, "std": 11, "min": 155, "max": 209},
        "didi":  {"mean": 182, "std": 13, "min": 158, "max": 212},
    },
    "McNuggets 10 piezas": {
        "rappi": {"mean": 149, "std": 10, "min": 129, "max": 169},
        "uber":  {"mean": 139, "std": 9,  "min": 119, "max": 159},
        "didi":  {"mean": 145, "std": 11, "min": 125, "max": 165},
    },
    "Papas a la Francesa Medianas": {
        "rappi": {"mean": 59,  "std": 5,  "min": 49,  "max": 75},
        "uber":  {"mean": 55,  "std": 5,  "min": 45,  "max": 69},
        "didi":  {"mean": 57,  "std": 6,  "min": 47,  "max": 72},
    },
}

# Zone type modifiers (premium pays more, peripheral saves on some)
ZONE_PRICE_MODIFIER = {
    "premium":            1.05,
    "residential_premium": 1.02,
    "commercial":         1.00,
    "residential_medium": 0.98,
    "peripheral":         0.96,
}

# Delivery fee structure (MXN)
DELIVERY_FEES = {
    "rappi": {
        "premium":            {"mean": 29, "std": 5,  "free_prob": 0.15},
        "residential_premium": {"mean": 25, "std": 5, "free_prob": 0.12},
        "commercial":         {"mean": 27, "std": 5,  "free_prob": 0.10},
        "residential_medium": {"mean": 35, "std": 7,  "free_prob": 0.08},
        "peripheral":         {"mean": 45, "std": 8,  "free_prob": 0.05},
    },
    "uber": {
        "premium":            {"mean": 19, "std": 4,  "free_prob": 0.25},
        "residential_premium": {"mean": 17, "std": 4, "free_prob": 0.22},
        "commercial":         {"mean": 20, "std": 5,  "free_prob": 0.18},
        "residential_medium": {"mean": 28, "std": 6,  "free_prob": 0.12},
        "peripheral":         {"mean": 38, "std": 7,  "free_prob": 0.08},
    },
    "didi": {
        "premium":            {"mean": 15, "std": 4,  "free_prob": 0.30},
        "residential_premium": {"mean": 14, "std": 4, "free_prob": 0.28},
        "commercial":         {"mean": 17, "std": 4,  "free_prob": 0.22},
        "residential_medium": {"mean": 22, "std": 5,  "free_prob": 0.18},
        "peripheral":         {"mean": 30, "std": 6,  "free_prob": 0.12},
    },
}

# Service fee (% of order subtotal)
SERVICE_FEE_RATE = {
    "rappi": {"mean": 0.08, "std": 0.02},
    "uber":  {"mean": 0.15, "std": 0.02},
    "didi":  {"mean": 0.10, "std": 0.02},
}

# ETA ranges (minutes)
ETA_CONFIG = {
    "rappi": {
        "premium":            {"min_base": 18, "max_base": 28},
        "residential_premium": {"min_base": 20, "max_base": 32},
        "commercial":         {"min_base": 22, "max_base": 35},
        "residential_medium": {"min_base": 25, "max_base": 40},
        "peripheral":         {"min_base": 35, "max_base": 55},
    },
    "uber": {
        "premium":            {"min_base": 20, "max_base": 30},
        "residential_premium": {"min_base": 22, "max_base": 34},
        "commercial":         {"min_base": 20, "max_base": 32},
        "residential_medium": {"min_base": 27, "max_base": 42},
        "peripheral":         {"min_base": 38, "max_base": 58},
    },
    "didi": {
        "premium":            {"min_base": 22, "max_base": 35},
        "residential_premium": {"min_base": 25, "max_base": 38},
        "commercial":         {"min_base": 23, "max_base": 36},
        "residential_medium": {"min_base": 30, "max_base": 48},
        "peripheral":         {"min_base": 42, "max_base": 65},
    },
}

# Promotion probability and typical labels
PROMO_CONFIG = {
    "rappi": {
        "prob":   0.35,
        "labels": ["2x1 bebidas", "20% descuento", "$30 de descuento", "Envío gratis en tu primera orden"],
    },
    "uber": {
        "prob":   0.50,
        "labels": ["15% off tu pedido", "Entrega gratis", "$25 de descuento", "Buy 1 Get 1"],
    },
    "didi": {
        "prob":   0.40,
        "labels": ["Cupón $20 off", "30% en tu primer pedido", "Envío gratis", "10% descuento"],
    },
}

STORE_NAMES = {
    "rappi": "McDonald's (via Rappi)",
    "uber":  "McDonald's",
    "didi":  "McDonald's DiDi",
}


def _sample_price(platform: str, product: str, zone_type: str) -> float:
    cfg = PRODUCT_PRICES[product][platform]
    modifier = ZONE_PRICE_MODIFIER.get(zone_type, 1.0)
    raw = np.random.normal(cfg["mean"] * modifier, cfg["std"])
    return round(max(cfg["min"], min(cfg["max"] * modifier * 1.1, raw)), 2)


def _sample_delivery_fee(platform: str, zone_type: str) -> float:
    cfg = DELIVERY_FEES[platform][zone_type]
    if random.random() < cfg["free_prob"]:
        return 0.0
    raw = np.random.normal(cfg["mean"], cfg["std"])
    return round(max(0, raw), 2)


def _sample_service_fee(platform: str, subtotal: float) -> float:
    cfg = SERVICE_FEE_RATE[platform]
    rate = np.random.normal(cfg["mean"], cfg["std"])
    rate = max(0.03, min(0.20, rate))
    return round(subtotal * rate, 2)


def _sample_eta(platform: str, zone_type: str) -> tuple:
    cfg = ETA_CONFIG[platform][zone_type]
    jitter = random.randint(-3, 5)
    eta_min = cfg["min_base"] + jitter
    eta_max = cfg["max_base"] + jitter + random.randint(0, 5)
    return max(10, eta_min), max(eta_min + 8, eta_max)


def _sample_promo(platform: str) -> tuple:
    cfg = PROMO_CONFIG[platform]
    if random.random() < cfg["prob"]:
        label = random.choice(cfg["labels"])
        # Estimate discount amount from label
        amount = None
        if "$" in label:
            import re
            m = re.search(r"\$(\d+)", label)
            if m:
                amount = float(m.group(1))
        elif "%" in label:
            import re
            m = re.search(r"(\d+)%", label)
            if m:
                amount = None   # % applied to product, track separately
        return True, label, amount
    return False, "", None


def generate_demo_data(
    addresses_file: Path = None,
    run_id: str = None,
    platforms: list = None,
    products: list = None,
    output_path: Path = None,
) -> pd.DataFrame:
    """Generate realistic synthetic competitive intelligence dataset."""
    addresses_file = addresses_file or (INPUT_DIR / "addresses.csv")
    run_id         = run_id or datetime.now().strftime("%Y%m%d_%H%M%S") + "_demo"
    platforms      = platforms or ["rappi", "uber", "didi"]
    products       = products or list(PRODUCT_PRICES.keys())
    output_path    = output_path or (PROCESSED_DIR / "competitive_prices_demo.csv")

    addresses = list(csv.DictReader(open(addresses_file, encoding="utf-8")))

    rows = []
    # Generate timestamps spread over past 3 hours
    base_time = datetime.now()

    for i, addr in enumerate(addresses):
        for platform in platforms:
            # Generate a fake scrape time
            scrape_time = base_time - timedelta(
                minutes=random.randint(0, 180)
            )

            zone_type   = addr["zone_type"]
            address_id  = addr["address_id"]

            # Store info (same for all products in same address×platform)
            eta_min, eta_max   = _sample_eta(platform, zone_type)
            delivery_fee       = _sample_delivery_fee(platform, zone_type)
            disc_visible, disc_label, disc_amount = _sample_promo(platform)

            for product in products:
                price      = _sample_price(platform, product, zone_type)
                svc_fee    = _sample_service_fee(platform, price)
                final_total = price + delivery_fee + svc_fee - (disc_amount or 0)

                row = {
                    "run_id":           run_id,
                    "scraped_at":       scrape_time.isoformat(),
                    "platform":         platform,
                    "country":          "MX",
                    "city":             addr["city"],
                    "address_id":       address_id,
                    "full_address":     addr["full_address"],
                    "zone_type":        zone_type,
                    "chain_name":       "mcdonalds",
                    "store_name":       STORE_NAMES[platform],
                    "store_available":  True,
                    "product_name":     product,
                    "product_canonical": product,
                    "product_price":    price,
                    "delivery_fee":     delivery_fee,
                    "service_fee":      svc_fee,
                    "discount_visible": disc_visible,
                    "discount_amount":  disc_amount,
                    "discount_label":   disc_label,
                    "eta_min":          eta_min,
                    "eta_max":          eta_max,
                    "subtotal":         round(price, 2),
                    "final_total":      round(final_total, 2),
                    "currency":         "MXN",
                    "screenshot_path":  f"data/screenshots/{platform}_{address_id}_store_page.png",
                    "status":           "success",
                    "error_message":    "",
                    "page_label":       "store_page",
                }
                rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Generated {len(df)} observations -> {output_path}")

    # Also write as "latest"
    latest_path = PROCESSED_DIR / "competitive_prices_latest.csv"
    df.to_csv(latest_path, index=False, encoding="utf-8")
    print(f"Also saved as: {latest_path}")

    return df


if __name__ == "__main__":
    generate_demo_data()
