"""
base_scraper.py — Abstract base class for all platform scrapers.

Provides:
- Playwright browser lifecycle management
- Random delay utilities (ethical rate limiting)
- Screenshot capture (success + error evidence)
- Retry logic with exponential backoff
- Logging setup per scraper
- Product matching against canonical names
"""

from __future__ import annotations
import asyncio
import json
import logging
import random
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import PriceObservation, StoreInfo
from config import (
    HEADLESS, BROWSER_TIMEOUT_MS, ELEMENT_TIMEOUT_MS,
    MIN_DELAY_BETWEEN_REQUESTS, MAX_DELAY_BETWEEN_REQUESTS,
    DELAY_BETWEEN_ADDRESSES, MAX_RETRIES, RETRY_DELAY_BASE,
    SCREENSHOTS_DIR, USER_AGENTS, STATUS, PRODUCT_MAP_FILE,
)


class BaseScraper(ABC):
    """
    Abstract base for Rappi, Uber Eats, and DiDi Food scrapers.
    Each subclass implements: set_location(), find_chain(), extract_store_info(),
    extract_product_price().
    """

    PLATFORM_ID: str = ""      # Override in subclass: "rappi", "uber", "didi"
    PLATFORM_NAME: str = ""    # Override: "Rappi", "Uber Eats", "DiDi Food"
    BASE_URL: str = ""

    def __init__(self, run_id: str, headless: bool = HEADLESS):
        self.run_id  = run_id
        self.headless = headless
        self.browser  = None
        self.context  = None
        self.page     = None
        self._product_map = self._load_product_map()
        self.logger   = self._setup_logger()
        self._ua      = random.choice(USER_AGENTS)

    # -- Logger ------------------------------------------------------------
    def _setup_logger(self) -> logging.Logger:
        from config import LOGS_DIR
        log_file = LOGS_DIR / f"{self.PLATFORM_ID}_{self.run_id}.log"
        logger = logging.getLogger(f"{self.PLATFORM_ID}_{self.run_id}")
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            fh.setFormatter(fmt)
            ch.setFormatter(fmt)
            logger.addHandler(fh)
            logger.addHandler(ch)
        return logger

    # -- Product map -------------------------------------------------------
    def _load_product_map(self) -> dict:
        try:
            with open(PRODUCT_MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"chains": {}, "anchor_chain": "mcdonalds"}

    def match_product(self, displayed_name: str, chain: str = "mcdonalds") -> Optional[str]:
        """
        Given a product name as displayed on a platform, return the canonical
        product key if it matches any known search term.
        Returns None if no match found.
        """
        chain_data = self._product_map.get("chains", {}).get(chain, {})
        products   = chain_data.get("products", {})
        displayed_lower = displayed_name.lower()
        for prod_key, prod_info in products.items():
            for term in prod_info.get("search_terms", []):
                if term.lower() in displayed_lower:
                    return prod_key
        return None

    def get_canonical_name(self, product_key: str, chain: str = "mcdonalds") -> str:
        chain_data = self._product_map.get("chains", {}).get(chain, {})
        products   = chain_data.get("products", {})
        return products.get(product_key, {}).get("canonical_name", product_key)

    # -- Delays (ethical scraping) -----------------------------------------
    async def _random_delay(self, min_s: float = None, max_s: float = None):
        min_s = min_s or MIN_DELAY_BETWEEN_REQUESTS
        max_s = max_s or MAX_DELAY_BETWEEN_REQUESTS
        delay = random.uniform(min_s, max_s)
        self.logger.debug(f"Sleeping {delay:.1f}s")
        await asyncio.sleep(delay)

    async def _address_delay(self):
        delay = random.uniform(DELAY_BETWEEN_ADDRESSES, DELAY_BETWEEN_ADDRESSES * 1.3)
        self.logger.debug(f"Address delay: {delay:.1f}s")
        await asyncio.sleep(delay)

    # -- Screenshots --------------------------------------------------------
    async def _screenshot(self, label: str, address_id: str) -> str:
        try:
            ts   = datetime.now().strftime("%H%M%S")
            name = f"{self.PLATFORM_ID}_{address_id}_{label}_{ts}.png"
            path = SCREENSHOTS_DIR / name
            await self.page.screenshot(path=str(path), full_page=False)
            self.logger.debug(f"Screenshot saved: {name}")
            return str(path)
        except Exception as e:
            self.logger.warning(f"Screenshot failed: {e}")
            return ""

    # -- Price parsing ------------------------------------------------------
    @staticmethod
    def parse_price(raw: str) -> Optional[float]:
        """
        Extract numeric price from strings like:
        '$89.00', 'MXN 89', '89.00', '$1,250.00', 'Gratis', 'Free'
        """
        if not raw:
            return None
        raw = raw.strip()
        if raw.lower() in ("gratis", "free", "$0", "0"):
            return 0.0
        cleaned = re.sub(r"[^\d.,]", "", raw)
        cleaned = cleaned.replace(",", "")
        try:
            return round(float(cleaned), 2)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_eta(raw: str) -> "Tuple[Optional[int], Optional[int]]":
        """
        Parse ETA strings like '20-35 min', '~25 min', '30 minutos', '1h 20 min'.
        Returns (eta_min, eta_max) in minutes.
        """
        if not raw:
            return None, None
        raw = raw.lower().strip()

        # Handle "1h 20 min" or "1 hr 20 min"
        hour_match = re.search(r"(\d+)\s*h(?:r|our)?s?\s*(\d+)?\s*m?i?n?", raw)
        if hour_match:
            hours = int(hour_match.group(1))
            mins  = int(hour_match.group(2)) if hour_match.group(2) else 0
            total = hours * 60 + mins
            return total, total

        # Handle ranges "20-35 min"
        range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", raw)
        if range_match:
            return int(range_match.group(1)), int(range_match.group(2))

        # Handle single "~25 min" or "25 min"
        single_match = re.search(r"~?(\d+)\s*min", raw)
        if single_match:
            v = int(single_match.group(1))
            return v, v

        # Bare number
        num_match = re.search(r"(\d+)", raw)
        if num_match:
            v = int(num_match.group(1))
            return v, v

        return None, None

    # -- Browser lifecycle -------------------------------------------------
    async def start(self):
        """Launch Playwright browser."""
        try:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()
            self.browser = await self._pw.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            self.context = await self.browser.new_context(
                user_agent=self._ua,
                viewport={"width": 1440, "height": 900},
                locale="es-MX",
                timezone_id="America/Mexico_City",
                extra_http_headers={
                    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
                },
            )
            self.page = await self.context.new_page()
            self.page.set_default_timeout(BROWSER_TIMEOUT_MS)
            self.page.set_default_navigation_timeout(BROWSER_TIMEOUT_MS)
            self.logger.info(f"Browser started for {self.PLATFORM_NAME}")
        except ImportError:
            self.logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            raise

    async def stop(self):
        """Close browser gracefully."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, "_pw"):
                await self._pw.stop()
            self.logger.info(f"Browser stopped for {self.PLATFORM_NAME}")
        except Exception as e:
            self.logger.warning(f"Error stopping browser: {e}")

    # -- Retry wrapper -----------------------------------------------------
    async def _with_retry(self, coro_fn, *args, max_retries: int = MAX_RETRIES, **kwargs):
        """Run an async function with exponential backoff retry."""
        last_exc = None
        for attempt in range(max_retries):
            try:
                return await coro_fn(*args, **kwargs)
            except Exception as e:
                last_exc = e
                wait = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 2)
                self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {wait:.1f}s")
                await asyncio.sleep(wait)
        raise last_exc

    # -- Abstract interface ------------------------------------------------
    @abstractmethod
    async def set_location(self, address: str, city: str) -> bool:
        """
        Navigate to platform and set delivery address.
        Returns True if location was set successfully.
        """
        ...

    @abstractmethod
    async def find_chain(self, chain_name: str) -> bool:
        """
        Search for the target chain (e.g. McDonald's).
        Returns True if found and opened.
        """
        ...

    @abstractmethod
    async def extract_store_info(self, address_id: str) -> StoreInfo:
        """
        Extract store-level data: ETA, delivery fee, service fee, promotions.
        Called after find_chain() succeeds.
        """
        ...

    @abstractmethod
    async def extract_product_price(
        self, product_key: str, chain: str = "mcdonalds"
    ) -> Optional[PriceObservation]:
        """
        Find and extract price for a specific product.
        Returns a PriceObservation or None if product not found.
        """
        ...

    # -- Main scrape loop for one address ---------------------------------
    async def scrape_address(
        self,
        address_row: dict,
        chain: str = "mcdonalds",
        product_keys: list = None,
    ) -> list[PriceObservation]:
        """
        Full scrape for one address: set location -> find store -> extract prices.
        Returns list of PriceObservation (one per product).
        """
        if product_keys is None:
            product_keys = self._product_map.get("priority_products", [])

        address_id  = address_row["address_id"]
        full_address = address_row["full_address"]
        city        = address_row["city"]
        zone_type   = address_row.get("zone_type", "unknown")

        self.logger.info(f"[{self.PLATFORM_NAME}] Scraping {address_id}: {full_address}")
        observations = []

        # -- Base observation template ----------------------------------
        base = PriceObservation(
            run_id       = self.run_id,
            platform     = self.PLATFORM_ID,
            city         = city,
            address_id   = address_id,
            full_address = full_address,
            zone_type    = zone_type,
            chain_name   = chain,
            currency     = "MXN",
        )

        try:
            # Step 1: Set location
            location_ok = await self._with_retry(self.set_location, full_address, city)
            if not location_ok:
                base.status        = STATUS["LOCATION_ERROR"]
                base.error_message = "Could not set delivery address"
                base.product_canonical = "N/A"
                base.screenshot_path = await self._screenshot("location_error", address_id)
                observations.append(base)
                return observations

            await self._random_delay()

            # Step 2: Find chain
            chain_ok = await self._with_retry(self.find_chain, chain)
            if not chain_ok:
                base.status           = STATUS["NOT_FOUND"]
                base.error_message    = f"Chain '{chain}' not found"
                base.store_available  = False
                base.product_canonical = "N/A"
                base.screenshot_path   = await self._screenshot("not_found", address_id)
                observations.append(base)
                return observations

            await self._random_delay()

            # Step 3: Extract store info
            store = await self.extract_store_info(address_id)
            await self._random_delay()

            # Step 4: Extract each product
            for prod_key in product_keys:
                obs = PriceObservation(
                    run_id            = self.run_id,
                    platform          = self.PLATFORM_ID,
                    city              = city,
                    address_id        = address_id,
                    full_address      = full_address,
                    zone_type         = zone_type,
                    chain_name        = chain,
                    store_name        = store.store_name,
                    store_available   = store.store_available,
                    product_canonical = self.get_canonical_name(prod_key, chain),
                    delivery_fee      = store.delivery_fee,
                    service_fee       = store.service_fee,
                    discount_visible  = store.discount_visible,
                    discount_label    = store.discount_label,
                    eta_min           = store.eta_min,
                    eta_max           = store.eta_max,
                    currency          = "MXN",
                    screenshot_path   = store.screenshot_path,
                )

                prod_obs = await self.extract_product_price(prod_key, chain)
                if prod_obs:
                    obs.product_name   = prod_obs.product_name
                    obs.product_price  = prod_obs.product_price
                    obs.discount_amount = prod_obs.discount_amount
                    obs.subtotal       = prod_obs.subtotal
                    obs.final_total    = prod_obs.final_total
                    obs.status         = STATUS["SUCCESS"]
                else:
                    obs.product_name   = prod_key
                    obs.status         = STATUS["PRODUCT_NA"]
                    obs.error_message  = f"Product '{prod_key}' not found on menu"

                observations.append(obs)
                await self._random_delay(1.5, 3.0)

        except Exception as e:
            self.logger.error(f"[{self.PLATFORM_NAME}] Error on {address_id}: {e}", exc_info=True)
            base.status        = STATUS["ERROR"]
            base.error_message = str(e)[:200]
            base.product_canonical = "N/A"
            base.screenshot_path = await self._screenshot("error", address_id)
            observations.append(base)

        await self._address_delay()
        return observations
