"""
models.py — Dataclasses for structured scraped observations.
Every scraped row is a PriceObservation. Clean, typed, serializable.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class PriceObservation:
    """
    One observation = one platform × one address × one product.
    This is the atomic unit of the competitive intelligence dataset.
    """
    # -- Run metadata ------------------------------------------------
    run_id:           str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    scraped_at:       str = field(default_factory=lambda: datetime.now().isoformat())

    # -- Platform & geography ---------------------------------------
    platform:         str = ""
    country:          str = "MX"
    city:             str = ""
    address_id:       str = ""
    full_address:     str = ""
    zone_type:        str = ""

    # -- Store info -------------------------------------------------
    chain_name:       str = ""
    store_name:       str = ""
    store_available:  bool = True

    # -- Product ---------------------------------------------------
    product_name:     str = ""          # As shown on platform
    product_canonical: str = ""         # Normalized canonical name
    product_price:    Optional[float] = None

    # -- Fees & pricing ---------------------------------------------
    delivery_fee:     Optional[float] = None
    service_fee:      Optional[float] = None
    discount_visible: bool = False
    discount_amount:  Optional[float] = None
    discount_label:   str = ""          # "2x1", "20% off", "$30 off", etc.
    eta_min:          Optional[int] = None    # minutes
    eta_max:          Optional[int] = None    # minutes
    subtotal:         Optional[float] = None
    final_total:      Optional[float] = None
    currency:         str = "MXN"

    # -- Evidence & status ------------------------------------------
    screenshot_path:  str = ""
    status:           str = "success"
    error_message:    str = ""
    page_label:       str = ""          # e.g. "store_page", "cart_page"

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def eta_midpoint(self) -> Optional[float]:
        if self.eta_min is not None and self.eta_max is not None:
            return (self.eta_min + self.eta_max) / 2
        return self.eta_min or self.eta_max

    @property
    def effective_total(self) -> Optional[float]:
        """Best estimate of what user actually pays."""
        if self.final_total is not None:
            return self.final_total
        if self.product_price is not None:
            total = self.product_price
            if self.delivery_fee:
                total += self.delivery_fee
            if self.service_fee:
                total += self.service_fee
            if self.discount_amount:
                total -= self.discount_amount
            return round(total, 2)
        return None


@dataclass
class StoreInfo:
    """Store-level metadata (independent of product)."""
    platform:         str = ""
    chain_name:       str = ""
    store_name:       str = ""
    address_id:       str = ""
    store_available:  bool = True
    delivery_fee:     Optional[float] = None
    service_fee:      Optional[float] = None
    eta_min:          Optional[int] = None
    eta_max:          Optional[int] = None
    discount_visible: bool = False
    discount_label:   str = ""
    promotions:       list = field(default_factory=list)
    screenshot_path:  str = ""
    status:           str = "success"
    error_message:    str = ""


@dataclass
class ScrapeSession:
    """Metadata for a complete scraping run."""
    run_id:           str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    started_at:       str = field(default_factory=lambda: datetime.now().isoformat())
    platforms:        list = field(default_factory=list)
    addresses_total:  int = 0
    addresses_done:   int = 0
    observations:     int = 0
    success_count:    int = 0
    error_count:      int = 0
    blocked_count:    int = 0

    def summary(self) -> dict:
        return {
            "run_id":          self.run_id,
            "started_at":      self.started_at,
            "platforms":       self.platforms,
            "addresses_total": self.addresses_total,
            "addresses_done":  self.addresses_done,
            "observations":    self.observations,
            "success_rate":    round(self.success_count / max(self.observations, 1), 3),
            "error_count":     self.error_count,
            "blocked_count":   self.blocked_count,
        }
