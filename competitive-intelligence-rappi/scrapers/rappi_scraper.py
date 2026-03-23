"""
rappi_scraper.py — Playwright-based scraper for Rappi Mexico (rappi.com.mx).

Flow:
1. Open rappi.com.mx
2. Click address input -> type address -> select from autocomplete
3. Navigate to Restaurantes -> search "McDonald's"
4. Extract ETA, delivery fee, promotions from store card/page
5. Open store -> extract product prices from menu
6. Capture screenshots as evidence at each key step
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional

from base_scraper import BaseScraper
from models import PriceObservation, StoreInfo
from config import STATUS, ELEMENT_TIMEOUT_MS, SCREENSHOTS_DIR


class RappiScraper(BaseScraper):

    PLATFORM_ID   = "rappi"
    PLATFORM_NAME = "Rappi"
    BASE_URL      = "https://www.rappi.com.mx"

    # -- Selector registry -------------------------------------------------
    # Selectors are ordered by reliability. We try each in sequence.
    # If Rappi changes HTML, update here — business logic stays intact.
    SELECTORS = {
        "address_input": [
            "input[placeholder*='dirección']",
            "input[placeholder*='Ingresa tu']",
            "[data-testid='address-input']",
            "input[name='address']",
            ".address-input input",
        ],
        "address_suggestion": [
            "[data-testid='address-suggestion']",
            ".suggestion-item",
            "li[role='option']",
            ".pac-item",                  # Google Places autocomplete
        ],
        "search_input": [
            "input[placeholder*='Buscar']",
            "input[placeholder*='buscar']",
            "[data-testid='search-input']",
            "input[type='search']",
        ],
        "store_card": [
            "[data-testid='store-card']",
            ".store-card",
            "[class*='restaurant-card']",
            "[class*='StoreCard']",
        ],
        "eta_text": [
            "[data-testid='eta']",
            "[class*='eta']",
            "[class*='delivery-time']",
            "span:has-text('min')",
        ],
        "delivery_fee": [
            "[data-testid='delivery-fee']",
            "[class*='delivery-fee']",
            "[class*='shipping-cost']",
            "span:has-text('Envío')",
        ],
        "product_item": [
            "[data-testid='menu-item']",
            "[class*='menu-item']",
            "[class*='MenuItem']",
            ".product-card",
        ],
        "product_price": [
            "[data-testid='item-price']",
            "[class*='price']",
            "[class*='Price']",
            "span:has-text('$')",
        ],
    }

    def _try_selector(self, selector_list: list) -> str:
        """Return a CSS selector list joined for Playwright's first match."""
        return ", ".join(selector_list)

    # -- 1. Set location ---------------------------------------------------
    async def set_location(self, address: str, city: str) -> bool:
        try:
            self.logger.info(f"[Rappi] Navigating to {self.BASE_URL}")
            await self.page.goto(self.BASE_URL, wait_until="networkidle")
            await self._random_delay(2, 4)

            # Try to find address input
            addr_selector = self._try_selector(self.SELECTORS["address_input"])
            addr_el = self.page.locator(addr_selector).first
            if not await addr_el.is_visible(timeout=8_000):
                # Sometimes Rappi shows a location modal on load
                modal_input = self.page.locator("input").first
                await modal_input.click()
            else:
                await addr_el.click()

            await self._random_delay(0.5, 1.5)
            await addr_el.fill(address)
            await self._random_delay(1.5, 2.5)  # Wait for autocomplete

            # Select first autocomplete suggestion
            suggestion_selector = self._try_selector(self.SELECTORS["address_suggestion"])
            suggestions = self.page.locator(suggestion_selector)
            count = await suggestions.count()

            if count > 0:
                await suggestions.first.click()
                await self._random_delay(2, 3)
                self.logger.info(f"[Rappi] Location set: {address}")
                return True
            else:
                # Try pressing Enter as fallback
                await addr_el.press("Enter")
                await self._random_delay(2, 3)
                self.logger.warning(f"[Rappi] No autocomplete suggestions, pressed Enter")
                return True  # Optimistic — let find_chain verify

        except Exception as e:
            self.logger.error(f"[Rappi] set_location failed: {e}")
            return False

    # -- 2. Find chain -----------------------------------------------------
    async def find_chain(self, chain_name: str) -> bool:
        try:
            chain_info = self._product_map["chains"].get(chain_name, {})
            display_names = chain_info.get("display_names", ["McDonald's"])
            search_term   = display_names[0]

            # Navigate to search or use search bar
            search_selector = self._try_selector(self.SELECTORS["search_input"])
            search_el = self.page.locator(search_selector).first

            if await search_el.is_visible(timeout=5_000):
                await search_el.click()
                await search_el.fill(search_term)
                await self.page.keyboard.press("Enter")
                await self._random_delay(2, 3)
            else:
                # Navigate directly via URL search
                search_url = f"{self.BASE_URL}/restaurantes?query={search_term.replace(' ', '+')}"
                await self.page.goto(search_url, wait_until="networkidle")
                await self._random_delay(2, 3)

            # Check results
            store_selector = self._try_selector(self.SELECTORS["store_card"])
            stores = self.page.locator(store_selector)
            count = await stores.count()

            if count == 0:
                self.logger.warning(f"[Rappi] No stores found for '{search_term}'")
                return False

            # Try to click the first McDonald's match
            for name in display_names:
                store_link = self.page.get_by_text(name, exact=False).first
                if await store_link.is_visible(timeout=3_000):
                    await store_link.click()
                    await self._random_delay(2, 3)
                    self.logger.info(f"[Rappi] Opened store: {name}")
                    return True

            # Fallback: click first store card
            await stores.first.click()
            await self._random_delay(2, 3)
            return True

        except Exception as e:
            self.logger.error(f"[Rappi] find_chain failed: {e}")
            return False

    # -- 3. Extract store info ---------------------------------------------
    async def extract_store_info(self, address_id: str) -> StoreInfo:
        store = StoreInfo(
            platform   = self.PLATFORM_ID,
            address_id = address_id,
            chain_name = "mcdonalds",
        )
        try:
            # ETA
            for sel in self.SELECTORS["eta_text"]:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2_000):
                    eta_text = await el.text_content()
                    store.eta_min, store.eta_max = self.parse_eta(eta_text or "")
                    if store.eta_min:
                        break

            # Delivery fee
            for sel in self.SELECTORS["delivery_fee"]:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2_000):
                    fee_text = await el.text_content()
                    if fee_text:
                        store.delivery_fee = self.parse_price(fee_text)
                        break

            # Store name
            h1 = self.page.locator("h1").first
            if await h1.is_visible(timeout=2_000):
                store.store_name = (await h1.text_content() or "").strip()

            # Promotions (look for discount badges)
            promo_selectors = [
                "[class*='promo']", "[class*='discount']",
                "[class*='offer']", "[class*='badge']",
                "span:has-text('%')", "span:has-text('Gratis')",
            ]
            for sel in promo_selectors:
                promos = self.page.locator(sel)
                count = await promos.count()
                if count > 0:
                    store.discount_visible = True
                    texts = []
                    for i in range(min(count, 3)):
                        t = await promos.nth(i).text_content()
                        if t:
                            texts.append(t.strip())
                    store.discount_label = " | ".join(texts[:2])
                    store.promotions = texts
                    break

            # Screenshot of store page
            store.screenshot_path = await self._screenshot("store_page", address_id)
            store.status = STATUS["SUCCESS"]
            self.logger.info(f"[Rappi] Store info: ETA={store.eta_min}-{store.eta_max}min "
                             f"fee=${store.delivery_fee} promo={store.discount_visible}")

        except Exception as e:
            self.logger.warning(f"[Rappi] Partial store info for {address_id}: {e}")
            store.status        = STATUS["PARTIAL"]
            store.error_message = str(e)[:200]

        return store

    # -- 4. Extract product price ------------------------------------------
    async def extract_product_price(
        self, product_key: str, chain: str = "mcdonalds"
    ) -> Optional[PriceObservation]:
        try:
            chain_info  = self._product_map["chains"].get(chain, {})
            prod_info   = chain_info.get("products", {}).get(product_key, {})
            search_terms = prod_info.get("search_terms", [product_key])
            canonical    = prod_info.get("canonical_name", product_key)

            # Try each search term to find the product in the menu
            for term in search_terms:
                # Try by visible text
                item = self.page.get_by_text(term, exact=False).first
                if await item.is_visible(timeout=2_000):
                    # Get price from sibling/parent
                    parent = item.locator("xpath=../..")
                    price_el = parent.locator("[class*='price'], [class*='Price'], span:has-text('$')").first
                    if await price_el.is_visible(timeout=2_000):
                        price_text = await price_el.text_content()
                        price = self.parse_price(price_text or "")
                        if price is not None:
                            self.logger.info(f"[Rappi] {canonical}: ${price}")
                            return PriceObservation(
                                product_name      = term,
                                product_canonical = canonical,
                                product_price     = price,
                            )

            # Fallback: scroll and look for product cards
            product_selector = self._try_selector(self.SELECTORS["product_item"])
            items = self.page.locator(product_selector)
            count = await items.count()

            for i in range(min(count, 50)):
                try:
                    item = items.nth(i)
                    item_text = await item.text_content() or ""
                    for term in search_terms:
                        if term.lower() in item_text.lower():
                            # Extract price from this item
                            price_el = item.locator("[class*='price'], [class*='Price']").first
                            if await price_el.is_visible(timeout=1_000):
                                price_text = await price_el.text_content()
                                price = self.parse_price(price_text or "")
                                if price is not None:
                                    self.logger.info(f"[Rappi] Found {canonical} via scan: ${price}")
                                    return PriceObservation(
                                        product_name      = term,
                                        product_canonical = canonical,
                                        product_price     = price,
                                    )
                except Exception:
                    continue

            self.logger.warning(f"[Rappi] Product not found: {canonical}")
            return None

        except Exception as e:
            self.logger.error(f"[Rappi] extract_product_price failed for {product_key}: {e}")
            return None
