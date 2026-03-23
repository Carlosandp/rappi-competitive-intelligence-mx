"""
config.py — Central configuration for the Competitive Intelligence pipeline.
All constants, paths, platform settings and scraping parameters live here.
"""
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

# -- Project paths ---------------------------------------------------------
BASE_DIR       = Path(__file__).parent.parent
DATA_DIR       = BASE_DIR / "data"
INPUT_DIR      = DATA_DIR / "input"
RAW_DIR        = DATA_DIR / "raw"
PROCESSED_DIR  = DATA_DIR / "processed"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
REPORTS_DIR    = BASE_DIR / "reports"
LOGS_DIR       = BASE_DIR / "logs"

for d in [RAW_DIR, PROCESSED_DIR, SCREENSHOTS_DIR, REPORTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# -- Input files ------------------------------------------------------------
ADDRESSES_FILE   = INPUT_DIR / "addresses.csv"
PRODUCT_MAP_FILE = INPUT_DIR / "product_map.json"

# -- Run metadata -----------------------------------------------------------
RUN_ID       = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_CSV   = PROCESSED_DIR / f"competitive_prices_{RUN_ID}.csv"
LATEST_CSV   = PROCESSED_DIR / "competitive_prices_latest.csv"

# -- Scraping settings ------------------------------------------------------
HEADLESS             = True          # Set False for debugging
BROWSER_TIMEOUT_MS   = 30_000        # 30s page load timeout
ELEMENT_TIMEOUT_MS   = 10_000        # 10s element wait
SCREENSHOT_ON_ERROR  = True
SCREENSHOT_ON_SUCCESS = True

# Rate limiting — ethical scraping
MIN_DELAY_BETWEEN_REQUESTS = 2.5    # seconds
MAX_DELAY_BETWEEN_REQUESTS = 5.0    # seconds
DELAY_BETWEEN_ADDRESSES    = 8.0    # seconds between address changes
MAX_RETRIES                = 3
RETRY_DELAY_BASE           = 10.0   # exponential backoff base

# -- Platform configuration -------------------------------------------------
PLATFORMS = {
    "rappi": {
        "name": "Rappi",
        "base_url": "https://www.rappi.com.mx",
        "country_code": "MX",
        "enabled": True,
        "robots_txt": "https://www.rappi.com.mx/robots.txt",
        "user_agent_hint": "desktop",
    },
    "uber": {
        "name": "Uber Eats",
        "base_url": "https://www.ubereats.com/mx",
        "country_code": "MX",
        "enabled": True,
        "robots_txt": "https://www.ubereats.com/robots.txt",
        "user_agent_hint": "desktop",
    },
    "didi": {
        "name": "DiDi Food",
        "base_url": "https://food.didiglobal.com/mx",
        "country_code": "MX",
        "enabled": True,
        "robots_txt": "https://food.didiglobal.com/robots.txt",
        "user_agent_hint": "desktop",
    },
}

# -- Browser user agents (rotate to avoid simple detection) ----------------
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

# -- Output column schema --------------------------------------------------
OUTPUT_COLUMNS = [
    "run_id",
    "scraped_at",
    "platform",
    "country",
    "city",
    "address_id",
    "full_address",
    "zone_type",
    "chain_name",
    "store_name",
    "store_available",
    "product_name",
    "product_canonical",
    "product_price",
    "delivery_fee",
    "service_fee",
    "discount_visible",
    "discount_amount",
    "discount_label",
    "eta_min",
    "eta_max",
    "subtotal",
    "final_total",
    "currency",
    "screenshot_path",
    "status",
    "error_message",
    "page_label",
]

# -- Status codes -----------------------------------------------------------
STATUS = {
    "SUCCESS":        "success",
    "PARTIAL":        "partial",
    "NOT_FOUND":      "not_found",
    "BLOCKED":        "blocked",
    "TIMEOUT":        "timeout",
    "LOCATION_ERROR": "location_error",
    "PRODUCT_NA":     "product_not_available",
    "ERROR":          "error",
}

# -- Chain target -----------------------------------------------------------
TARGET_CHAIN = "mcdonalds"

# -- Analysis settings ------------------------------------------------------
BASELINE_PLATFORM   = "rappi"    # Platform used as price reference
CURRENCY            = "MXN"
PRICE_OUTLIER_SIGMA = 3.0        # Z-score threshold to flag outliers
MIN_SAMPLE_FOR_STAT = 3          # Min observations for statistical conclusions
