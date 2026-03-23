"""
didi_scraper.py — Playwright-based scraper for DiDi Food Mexico (food.didiglobal.com/mx).

DiDi Food has a simpler UI than Rappi/Uber, making it somewhat more stable to scrape.
Flow mirrors the other scrapers: set location -> find chain -> extract store info -> prices.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from base_scraper import BaseScraper
from models import PriceObservation, StoreInfo
from config import STATUS, ELEMENT_TIMEOUT_MS


class DidiScraper(BaseScraper):

    PLATFORM_ID   = "didi"
    PLATFORM_NAME = "DiDi Food"
    BASE_URL      = "https://food.didiglobal.com/mx"
    ALT_URL       = "https://food.didiglobal.com/mexico"

    SELECTORS = {
        "address_input": [
            "input[placeholder*='Ingresa']",
            "input[placeholder*='dirección']",
            "input[placeholder*='Dirección']",
            "[class*='address'] input",
            "[class*='location'] input",
            "input[type='text']",
        ],
        "address_suggestion": [
            "[class*='suggestion']",
            "[class*='dropdown'] li",
            "[role='option']",
            ".pac-item",
            "li:has(span)",
        ],
        "store_card": [
            "[class*='restaurant-card']",
            "[class*='store-card']",
            "[class*='RestaurantCard']",
            "a[href*='/mx/restaurant']",
            "a[href*='/mexico/restaurant']",
        ],
        "eta_text": [
            "[class*='delivery-time']",
            "[class*='eta']",
            "[class*='Eta']",
            "span:has-text('min')",
        ],
        "delivery_fee": [
            "[class*='delivery-fee']",
            "[class*='shipping']",
            "span:has-text('Envío')",
            "span:has-text('envío')",
        ],
        "product_item": [
            "[class*='item-card']",
            "[class*='ItemCard']",
            "[class*='food-item']",
            "[class*='product-item']",
            ".menu-item",
        ],
    }

    def _try_selector(self, selector_list: list) -> str:
        return ", ".join(selector_list)

    # -- 1. Set location ---------------------------------------------------
    async def set_location(self, address: str, city: str) -> bool:
        try:
            self.logger.info(f"[DiDi] Navigating to {self.BASE_URL}")
            # Try primary URL
            response = await self.page.goto(self.BASE_URL, wait_until="networkidle")
            if not response or response.status >= 400:
                await self.page.goto(self.ALT_URL, wait_until="networkidle")
            await self._random_delay(2, 4)

            # DiDi sometimes shows language selector or location prompt
            try:
                for dismiss_text in ["Continuar", "Aceptar", "OK", "Entendido"]:
                    btn = self.page.get_by_text(dismiss_text, exact=True).first
                    if await btn.is_visible(timeout=2_000):
                        await btn.click()
                        await self._random_delay(0.5, 1)
                        break
            except Exception:
                pass

            addr_selector = self._try_selector(self.SELECTORS["address_input"])
            addr_el = self.page.locator(addr_selector).first

            # DiDi might show a map/location button first
            if not await addr_el.is_visible(timeout=6_000):
                for text in ["Ingresar dirección", "¿Dónde entregamos?", "Agregar dirección"]:
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

            if await suggestions.count() > 0:
                await suggestions.first.click()
                await self._random_delay(2, 3)
                self.logger.info(f"[DiDi] Location set: {address}")
                return True
            else:
                await addr_el.press("Enter")
                await self._random_delay(2, 3)
                return True

        except Exception as e:
            self.logger.error(f"[DiDi] set_location failed: {e}")
            return False

    # -- 2. Find chain -----------------------------------------------------
    async def find_chain(self, chain_name: str) -> bool:
        try:
            chain_info    = self._product_map["chains"].get(chain_name, {})
            display_names = chain_info.get("display_names", ["McDonald's"])
            search_term   = display_names[0]

            # Try search input
            search_selector = "input[placeholder*='Buscar'], input[placeholder*='buscar'], input[type='search']"
            search_el = self.page.locator(search_selector).first

            if await search_el.is_visible(timeout=4_000):
                await search_el.click()
                await search_el.fill(search_term)
                await self.page.keyboard.press("Enter")
                await self._random_delay(2, 3)
            else:
                # Try URL-based search
                search_url = f"{self.BASE_URL}?keyword={search_term.replace(' ', '+')}"
                await self.page.goto(search_url, wait_until="networkidle")
                await self._random_delay(2, 3)

            # Find store result
            for name in display_names:
                store_text = self.page.get_by_text(name, exact=False).first
                if await store_text.is_visible(timeout=4_000):
                    await store_text.click()
                    await self._random_delay(2, 3)
                    self.logger.info(f"[DiDi] Opened: {name}")
                    return True

            # Click first store card
            store_selector = self._try_selector(self.SELECTORS["store_card"])
            stores = self.page.locator(store_selector)
            if await stores.count() > 0:
                await stores.first.click()
                await self._random_delay(2, 3)
                return True

            self.logger.warning(f"[DiDi] Chain '{search_term}' not found")
            return False

        except Exception as e:
            self.logger.error(f"[DiDi] find_chain failed: {e}")
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

            # Delivery fee
            for sel in self.SELECTORS["delivery_fee"]:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2_000):
                    fee_text = await el.text_content()
                    if fee_text:
                        fee = self.parse_price(fee_text)
                        if fee is not None:
                            store.delivery_fee = fee
                            break

            # DiDi sometimes shows promotional labels prominently
            promo_selectors = [
                "[class*='coupon']", "[class*='promo']",
                "span:has-text('%')", "[class*='discount']",
                "span:has-text('gratis')", "span:has-text('Gratis')",
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
            self.logger.info(f"[DiDi] Store info: name={store.store_name} "
                             f"ETA={store.eta_min}-{store.eta_max}min fee=${store.delivery_fee}")

        except Exception as e:
            self.logger.warning(f"[DiDi] Partial store info for {address_id}: {e}")
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
                item = self.page.get_by_text(term, exact=False).first
                if await item.is_visible(timeout=2_000):
                    container = item.locator("xpath=../../..")
                    price_el = container.locator("span:has-text('$'), [class*='price']").first
                    if await price_el.is_visible(timeout=1_500):
                        price_text = await price_el.text_content()
                        price = self.parse_price(price_text or "")
                        if price and price > 0:
                            self.logger.info(f"[DiDi] {canonical}: ${price}")
                            return PriceObservation(
                                product_name      = term,
                                product_canonical = canonical,
                                product_price     = price,
                            )

            # Scroll scan
            for scroll_y in [500, 1000, 1500, 2000]:
                await self.page.evaluate(f"window.scrollTo(0, {scroll_y})")
                await self._random_delay(0.3, 0.7)
                for term in search_terms:
                    item = self.page.get_by_text(term, exact=False).first
                    if await item.is_visible(timeout=1_000):
                        container = item.locator("xpath=../../..")
                        price_el = container.locator("span:has-text('$'), [class*='price']").first
                        if await price_el.is_visible(timeout=1_000):
                            price_text = await price_el.text_content()
                            price = self.parse_price(price_text or "")
                            if price and price > 0:
                                return PriceObservation(
                                    product_name      = term,
                                    product_canonical = canonical,
                                    product_price     = price,
                                )

            self.logger.warning(f"[DiDi] Product not found: {canonical}")
            return None

        except Exception as e:
            self.logger.error(f"[DiDi] extract_product_price failed for {product_key}: {e}")
            return None
