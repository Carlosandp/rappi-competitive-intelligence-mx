"""
uber_scraper.py — Playwright-based scraper for Uber Eats Mexico (ubereats.com/mx).

Flow:
1. Open ubereats.com/mx
2. Set delivery address via location modal
3. Search for McDonald's -> open store
4. Extract ETA, fees, promotions
5. Extract product prices from menu
6. Screenshot evidence at each step
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional

from base_scraper import BaseScraper
from models import PriceObservation, StoreInfo
from config import STATUS, ELEMENT_TIMEOUT_MS


class UberEatsScraper(BaseScraper):

    PLATFORM_ID   = "uber"
    PLATFORM_NAME = "Uber Eats"
    BASE_URL      = "https://www.ubereats.com/mx"

    SELECTORS = {
        "address_input": [
            "input[placeholder*='Ingresa']",
            "input[placeholder*='Dirección']",
            "input[placeholder*='dirección']",
            "[data-testid='address-delivery-input']",
            "input[name='pl']",
            "#location-typeahead-home-input",
        ],
        "address_suggestion": [
            "[data-testid='address-suggestion']",
            "[class*='PlaceSuggestion']",
            "li[data-testid]",
            ".css-suggestion",
            "[role='option']",
        ],
        "store_card": [
            "[data-testid='store-card']",
            "[class*='StoreCard']",
            "[data-testid='rich-card']",
            "a[href*='/mx/store/']",
        ],
        "eta_text": [
            "[data-testid='store-eta']",
            "[class*='EtaRange']",
            "span:has-text('min')",
            "[class*='delivery-time']",
        ],
        "delivery_fee": [
            "[data-testid='delivery-fee']",
            "[class*='DeliveryFee']",
            "[class*='delivery-fee']",
        ],
        "service_fee": [
            "[data-testid='service-fee']",
            "[class*='ServiceFee']",
            "span:has-text('Tarifa de servicio')",
            "span:has-text('service fee')",
        ],
        "product_item": [
            "[data-testid='rich-text']",
            "[class*='MenuSection'] li",
            "[class*='MenuItem']",
            "[data-testid='menu-item']",
        ],
    }

    def _try_selector(self, selector_list: list) -> str:
        return ", ".join(selector_list)

    # -- 1. Set location ---------------------------------------------------
    async def set_location(self, address: str, city: str) -> bool:
        try:
            self.logger.info(f"[Uber] Navigating to {self.BASE_URL}")
            await self.page.goto(self.BASE_URL, wait_until="networkidle")
            await self._random_delay(2, 4)

            # Dismiss any cookie/location modal first
            try:
                accept_btn = self.page.get_by_text("Aceptar", exact=False).first
                if await accept_btn.is_visible(timeout=2_000):
                    await accept_btn.click()
                    await self._random_delay(0.5, 1)
            except Exception:
                pass

            addr_selector = self._try_selector(self.SELECTORS["address_input"])
            addr_el = self.page.locator(addr_selector).first

            if not await addr_el.is_visible(timeout=8_000):
                # Try clicking a "Deliver to" or "¿Dónde entregamos?" button
                for text in ["¿A dónde entregamos?", "Ingresa tu dirección", "Deliver to"]:
                    btn = self.page.get_by_text(text, exact=False).first
                    if await btn.is_visible(timeout=2_000):
                        await btn.click()
                        await self._random_delay(1, 2)
                        break
                addr_el = self.page.locator(addr_selector).first

            await addr_el.click()
            await addr_el.fill(address)
            await self._random_delay(1.5, 2.5)

            suggestion_selector = self._try_selector(self.SELECTORS["address_suggestion"])
            suggestions = self.page.locator(suggestion_selector)

            count = await suggestions.count()
            if count > 0:
                await suggestions.first.click()
                await self._random_delay(2, 3)

                # Confirm location if there's a "Search here" / "Buscar aquí" button
                for confirm_text in ["Buscar aquí", "Search here", "Confirmar"]:
                    btn = self.page.get_by_text(confirm_text, exact=False).first
                    if await btn.is_visible(timeout=2_000):
                        await btn.click()
                        await self._random_delay(1.5, 2.5)
                        break

                self.logger.info(f"[Uber] Location set: {address}")
                return True
            else:
                await addr_el.press("Enter")
                await self._random_delay(2, 3)
                return True

        except Exception as e:
            self.logger.error(f"[Uber] set_location failed: {e}")
            return False

    # -- 2. Find chain -----------------------------------------------------
    async def find_chain(self, chain_name: str) -> bool:
        try:
            chain_info    = self._product_map["chains"].get(chain_name, {})
            display_names = chain_info.get("display_names", ["McDonald's"])
            search_term   = display_names[0]

            # Navigate to search
            search_url = f"{self.BASE_URL}/find-food?q={search_term.replace(' ', '%20')}"
            await self.page.goto(search_url, wait_until="networkidle")
            await self._random_delay(2, 3)

            # Or use search input if available
            search_selector = "input[placeholder*='Buscar'], input[data-testid*='search']"
            search_el = self.page.locator(search_selector).first
            if await search_el.is_visible(timeout=3_000):
                await search_el.fill(search_term)
                await self.page.keyboard.press("Enter")
                await self._random_delay(2, 3)

            # Find and click store
            for name in display_names:
                # Try store cards
                store_link = self.page.get_by_text(name, exact=False).first
                if await store_link.is_visible(timeout=4_000):
                    await store_link.click()
                    await self._random_delay(2, 3)
                    self.logger.info(f"[Uber] Opened: {name}")
                    return True

            # Fallback: click first result
            store_selector = self._try_selector(self.SELECTORS["store_card"])
            stores = self.page.locator(store_selector)
            if await stores.count() > 0:
                await stores.first.click()
                await self._random_delay(2, 3)
                return True

            self.logger.warning(f"[Uber] Chain '{search_term}' not found")
            return False

        except Exception as e:
            self.logger.error(f"[Uber] find_chain failed: {e}")
            return False

    # -- 3. Extract store info ---------------------------------------------
    async def extract_store_info(self, address_id: str) -> StoreInfo:
        store = StoreInfo(
            platform   = self.PLATFORM_ID,
            address_id = address_id,
            chain_name = "mcdonalds",
        )
        try:
            # Store name
            h1 = self.page.locator("h1").first
            if await h1.is_visible(timeout=3_000):
                store.store_name = (await h1.text_content() or "").strip()

            # ETA
            for sel in self.SELECTORS["eta_text"]:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2_000):
                    eta_text = await el.text_content()
                    store.eta_min, store.eta_max = self.parse_eta(eta_text or "")
                    if store.eta_min:
                        break

            # Delivery fee — Uber often shows it on store page header
            for sel in self.SELECTORS["delivery_fee"]:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2_000):
                    fee_text = await el.text_content()
                    if fee_text:
                        fee = self.parse_price(fee_text)
                        if fee is not None:
                            store.delivery_fee = fee
                            break

            # Service fee
            for sel in self.SELECTORS["service_fee"]:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2_000):
                    fee_text = await el.text_content()
                    if fee_text:
                        fee = self.parse_price(fee_text)
                        if fee is not None:
                            store.service_fee = fee
                            break

            # Promotions
            promo_selectors = [
                "span:has-text('%')", "[class*='promo']",
                "[class*='Promo']", "[class*='discount']",
                "span:has-text('Gratis')",
            ]
            for sel in promo_selectors:
                promos = self.page.locator(sel)
                if await promos.count() > 0:
                    store.discount_visible = True
                    texts = []
                    for i in range(min(await promos.count(), 3)):
                        t = await promos.nth(i).text_content()
                        if t:
                            texts.append(t.strip())
                    store.discount_label = " | ".join(texts[:2])
                    store.promotions = texts
                    break

            store.screenshot_path = await self._screenshot("store_page", address_id)
            store.status = STATUS["SUCCESS"]
            self.logger.info(f"[Uber] Store info: name={store.store_name} "
                             f"ETA={store.eta_min}-{store.eta_max}min fee=${store.delivery_fee}")

        except Exception as e:
            self.logger.warning(f"[Uber] Partial store info for {address_id}: {e}")
            store.status        = STATUS["PARTIAL"]
            store.error_message = str(e)[:200]

        return store

    # -- 4. Extract product price ------------------------------------------
    async def extract_product_price(
        self, product_key: str, chain: str = "mcdonalds"
    ) -> Optional[PriceObservation]:
        try:
            chain_info   = self._product_map["chains"].get(chain, {})
            prod_info    = chain_info.get("products", {}).get(product_key, {})
            search_terms = prod_info.get("search_terms", [product_key])
            canonical    = prod_info.get("canonical_name", product_key)

            for term in search_terms:
                # Direct text lookup
                item = self.page.get_by_text(term, exact=False).first
                if await item.is_visible(timeout=2_000):
                    # Price is often in a sibling span
                    container = item.locator("xpath=../../..")
                    price_el = container.locator("[class*='price'], [class*='Price'], span:has-text('$')").first
                    if await price_el.is_visible(timeout=1_500):
                        price_text = await price_el.text_content()
                        price = self.parse_price(price_text or "")
                        if price and price > 0:
                            self.logger.info(f"[Uber] {canonical}: ${price}")
                            return PriceObservation(
                                product_name      = term,
                                product_canonical = canonical,
                                product_price     = price,
                            )

            # Scroll-based scan
            await self.page.evaluate("window.scrollTo(0, 0)")
            for scroll_y in [500, 1000, 1500, 2000, 2500]:
                await self.page.evaluate(f"window.scrollTo(0, {scroll_y})")
                await self._random_delay(0.3, 0.6)
                for term in search_terms:
                    item = self.page.get_by_text(term, exact=False).first
                    if await item.is_visible(timeout=1_000):
                        container = item.locator("xpath=../../..")
                        price_el = container.locator("[class*='price'], [class*='Price']").first
                        if await price_el.is_visible(timeout=1_000):
                            price_text = await price_el.text_content()
                            price = self.parse_price(price_text or "")
                            if price and price > 0:
                                self.logger.info(f"[Uber] Found {canonical} via scroll: ${price}")
                                return PriceObservation(
                                    product_name      = term,
                                    product_canonical = canonical,
                                    product_price     = price,
                                )

            self.logger.warning(f"[Uber] Product not found: {canonical}")
            return None

        except Exception as e:
            self.logger.error(f"[Uber] extract_product_price failed for {product_key}: {e}")
            return None
