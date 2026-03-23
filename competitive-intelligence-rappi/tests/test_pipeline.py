"""
tests/test_pipeline.py — Test suite for the competitive intelligence pipeline.
Tests scraper utilities, data parsing, normalization, and insight generation.
Run: pytest tests/ -v
"""
from __future__ import annotations

import sys
import csv
import json
import tempfile
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "scrapers"))
sys.path.insert(0, str(BASE_DIR / "analysis"))


# ======================================================================
# A. Price and ETA parsing (BaseScraper static methods)
# ======================================================================
class TestPriceParsing:
    def _parse(self, s):
        """Replicate BaseScraper.parse_price without importing Playwright."""
        import re
        if not s:
            return None
        s = s.strip()
        if s.lower() in ("gratis", "free", "$0", "0"):
            return 0.0
        cleaned = re.sub(r"[^\d.,]", "", s).replace(",", "")
        try:
            return round(float(cleaned), 2)
        except (ValueError, TypeError):
            return None

    def test_dollar_format(self):
        assert self._parse("$89.00") == 89.0

    def test_mxn_format(self):
        assert self._parse("MXN 89") == 89.0

    def test_comma_thousands(self):
        assert self._parse("$1,250.00") == 1250.0

    def test_free_gratis(self):
        assert self._parse("Gratis") == 0.0

    def test_free_english(self):
        assert self._parse("Free") == 0.0

    def test_none_input(self):
        assert self._parse(None) is None

    def test_empty_string(self):
        assert self._parse("") is None

    def test_integer_price(self):
        assert self._parse("149") == 149.0


class TestEtaParsing:
    def _parse_eta(self, s):
        import re
        if not s:
            return None, None
        s = s.lower().strip()
        hour_match = re.search(r"(\d+)\s*h(?:r|our)?s?\s*(\d+)?\s*m?i?n?", s)
        if hour_match:
            hours = int(hour_match.group(1))
            mins  = int(hour_match.group(2)) if hour_match.group(2) else 0
            total = hours * 60 + mins
            return total, total
        range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", s)
        if range_match:
            return int(range_match.group(1)), int(range_match.group(2))
        single_match = re.search(r"~?(\d+)\s*min", s)
        if single_match:
            v = int(single_match.group(1))
            return v, v
        num_match = re.search(r"(\d+)", s)
        if num_match:
            v = int(num_match.group(1))
            return v, v
        return None, None

    def test_range_format(self):
        lo, hi = self._parse_eta("20-35 min")
        assert lo == 20 and hi == 35

    def test_approx_format(self):
        lo, hi = self._parse_eta("~25 min")
        assert lo == 25 and hi == 25

    def test_single_min(self):
        lo, hi = self._parse_eta("30 min")
        assert lo == 30 and hi == 30

    def test_hour_format(self):
        lo, hi = self._parse_eta("1h 20 min")
        assert lo == 80 and hi == 80

    def test_none_input(self):
        lo, hi = self._parse_eta(None)
        assert lo is None and hi is None

    def test_dash_separator(self):
        lo, hi = self._parse_eta("15 – 30 min")
        assert lo == 15 and hi == 30


# ======================================================================
# B. Models
# ======================================================================
class TestPriceObservation:
    def test_to_dict(self):
        from models import PriceObservation
        obs = PriceObservation(
            platform="rappi", city="CDMX", product_canonical="Big Mac",
            product_price=105.0, delivery_fee=25.0, service_fee=8.4,
        )
        d = obs.to_dict()
        assert d["platform"] == "rappi"
        assert d["product_price"] == 105.0
        assert d["delivery_fee"] == 25.0

    def test_eta_midpoint(self):
        from models import PriceObservation
        obs = PriceObservation(eta_min=20, eta_max=35)
        assert obs.eta_midpoint == 27.5

    def test_effective_total(self):
        from models import PriceObservation
        obs = PriceObservation(
            product_price=100.0, delivery_fee=25.0, service_fee=8.0, discount_amount=10.0
        )
        assert obs.effective_total == 123.0

    def test_effective_total_uses_final_if_set(self):
        from models import PriceObservation
        obs = PriceObservation(product_price=100.0, delivery_fee=25.0, final_total=110.0)
        assert obs.effective_total == 110.0


# ======================================================================
# C. Addresses CSV
# ======================================================================
class TestAddresses:
    def test_file_exists(self):
        assert (BASE_DIR / "data" / "input" / "addresses.csv").exists()

    def test_24_addresses(self):
        rows = list(csv.DictReader(open(BASE_DIR / "data" / "input" / "addresses.csv")))
        assert len(rows) == 24

    def test_required_columns(self):
        rows = list(csv.DictReader(open(BASE_DIR / "data" / "input" / "addresses.csv")))
        required = {"address_id", "city", "full_address", "zone_type", "latitude", "longitude"}
        assert required.issubset(set(rows[0].keys()))

    def test_three_cities(self):
        rows = list(csv.DictReader(open(BASE_DIR / "data" / "input" / "addresses.csv")))
        cities = {r["city"] for r in rows}
        assert len(cities) == 3

    def test_zone_types_valid(self):
        rows = list(csv.DictReader(open(BASE_DIR / "data" / "input" / "addresses.csv")))
        valid_types = {"premium","residential_premium","commercial","residential_medium","peripheral"}
        for r in rows:
            assert r["zone_type"] in valid_types, f"Invalid zone_type: {r['zone_type']}"

    def test_cdmx_12_addresses(self):
        rows = list(csv.DictReader(open(BASE_DIR / "data" / "input" / "addresses.csv")))
        cdmx = [r for r in rows if "Ciudad de México" in r["city"]]
        assert len(cdmx) == 12

    def test_gdl_6_addresses(self):
        rows = list(csv.DictReader(open(BASE_DIR / "data" / "input" / "addresses.csv")))
        gdl = [r for r in rows if r["city"] == "Guadalajara"]
        assert len(gdl) == 6

    def test_mty_6_addresses(self):
        rows = list(csv.DictReader(open(BASE_DIR / "data" / "input" / "addresses.csv")))
        mty = [r for r in rows if r["city"] == "Monterrey"]
        assert len(mty) == 6

    def test_no_duplicate_address_ids(self):
        rows = list(csv.DictReader(open(BASE_DIR / "data" / "input" / "addresses.csv")))
        ids = [r["address_id"] for r in rows]
        assert len(ids) == len(set(ids)), "Duplicate address IDs found"


# ======================================================================
# D. Product map
# ======================================================================
class TestProductMap:
    def _load(self):
        with open(BASE_DIR / "data" / "input" / "product_map.json") as f:
            return json.load(f)

    def test_file_exists(self):
        assert (BASE_DIR / "data" / "input" / "product_map.json").exists()

    def test_mcdonalds_chain(self):
        pm = self._load()
        assert "mcdonalds" in pm["chains"]

    def test_priority_products(self):
        pm = self._load()
        assert len(pm["priority_products"]) >= 3

    def test_each_product_has_search_terms(self):
        pm = self._load()
        for chain, info in pm["chains"].items():
            for prod_key, prod_info in info.get("products", {}).items():
                assert len(prod_info.get("search_terms", [])) >= 1

    def test_anchor_chain_set(self):
        pm = self._load()
        assert pm["anchor_chain"] in pm["chains"]


# ======================================================================
# E. Demo data generation
# ======================================================================
class TestDemoDataGeneration:
    def test_generates_288_rows(self):
        from generate_demo_data import generate_demo_data
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "test_demo.csv"
            df = generate_demo_data(output_path=out)
            # 24 addresses × 3 platforms × 4 products = 288
            assert len(df) == 288

    def test_three_platforms(self):
        from generate_demo_data import generate_demo_data
        with tempfile.TemporaryDirectory() as tmp:
            df = generate_demo_data(output_path=Path(tmp) / "x.csv")
            assert df["platform"].nunique() == 3

    def test_all_statuses_success(self):
        from generate_demo_data import generate_demo_data
        with tempfile.TemporaryDirectory() as tmp:
            df = generate_demo_data(output_path=Path(tmp) / "x.csv")
            assert (df["status"] == "success").all()

    def test_prices_in_realistic_range(self):
        from generate_demo_data import generate_demo_data
        with tempfile.TemporaryDirectory() as tmp:
            df = generate_demo_data(output_path=Path(tmp) / "x.csv")
            assert df["product_price"].min() >= 40
            assert df["product_price"].max() <= 260

    def test_delivery_fee_non_negative(self):
        from generate_demo_data import generate_demo_data
        with tempfile.TemporaryDirectory() as tmp:
            df = generate_demo_data(output_path=Path(tmp) / "x.csv")
            assert (df["delivery_fee"] >= 0).all()

    def test_eta_min_less_than_max(self):
        from generate_demo_data import generate_demo_data
        with tempfile.TemporaryDirectory() as tmp:
            df = generate_demo_data(output_path=Path(tmp) / "x.csv")
            assert (df["eta_min"] <= df["eta_max"]).all()


# ======================================================================
# F. Normalization
# ======================================================================
class TestNormalization:
    @staticmethod
    def _get_demo():
        from generate_demo_data import generate_demo_data
        from normalize import normalize_dataset
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            df_raw = generate_demo_data(output_path=Path(tmp) / "x.csv")
        return normalize_dataset(df_raw)

    def test_platform_label_column(self):
        df = self._get_demo()
        assert "platform_label" in df.columns
        assert set(df["platform_label"].unique()) == {"Rappi", "Uber Eats", "DiDi Food"}

    def test_eta_midpoint_computed(self):
        df = self._get_demo()
        assert "eta_midpoint" in df.columns
        assert df["eta_midpoint"].notna().mean() > 0.9

    def test_effective_total_computed(self):
        df = self._get_demo()
        assert "effective_total" in df.columns
        assert df["effective_total"].notna().mean() > 0.8

    def test_has_price_flag(self):
        df = self._get_demo()
        assert "has_price" in df.columns
        assert df["has_price"].sum() > 200

    def test_city_short_column(self):
        df = self._get_demo()
        assert "city_short" in df.columns
        assert "CDMX" in df["city_short"].values

    def test_price_vs_rappi_column(self):
        df = self._get_demo()
        assert "price_vs_rappi_pct" in df.columns


# ======================================================================
# G. Insights
# ======================================================================
class TestInsights:
    @staticmethod
    def _get_norm():
        from generate_demo_data import generate_demo_data
        from normalize import normalize_dataset
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            df_raw = generate_demo_data(output_path=Path(tmp) / "x.csv")
        return normalize_dataset(df_raw)

    def test_generates_5_insights(self):
        from insights import generate_insights
        df = self._get_norm()
        ins = generate_insights(df)
        assert len(ins) == 5

    def test_each_insight_has_required_fields(self):
        from insights import generate_insights
        df = self._get_norm()
        required = {"id","title","category","finding","impact","recommendation","severity"}
        for ins in generate_insights(df):
            assert required.issubset(set(ins.keys()))

    def test_insight_ids_unique(self):
        from insights import generate_insights
        df = self._get_norm()
        ids = [ins["id"] for ins in generate_insights(df)]
        assert len(ids) == len(set(ids))

    def test_severity_valid(self):
        from insights import generate_insights
        df = self._get_norm()
        valid = {"high","medium","low"}
        for ins in generate_insights(df):
            assert ins["severity"] in valid

    def test_rappi_price_higher_than_uber(self):
        """Verify synthetic data shows Rappi slightly more expensive (by design)."""
        df = self._get_norm()
        rappi_avg = df[df["platform"]=="rappi"]["product_price"].mean()
        uber_avg  = df[df["platform"]=="uber"]["product_price"].mean()
        assert rappi_avg > uber_avg


# ======================================================================
# H. HTML report
# ======================================================================
class TestHTMLReport:
    def test_generates_html(self):
        from generate_demo_data import generate_demo_data
        from report_generator import generate_html_report
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            df_raw = generate_demo_data(output_path=Path(tmp) / "x.csv")
            html = generate_html_report(df_raw)
        assert "<html" in html and "</html>" in html

    def test_html_has_insights(self):
        from generate_demo_data import generate_demo_data
        from report_generator import generate_html_report
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            df_raw = generate_demo_data(output_path=Path(tmp) / "x.csv")
            html = generate_html_report(df_raw)
        assert "insight-card" in html
        assert "HALLAZGO" in html
        assert "RECOMENDACIÓN" in html

    def test_html_has_all_platforms(self):
        from generate_demo_data import generate_demo_data
        from report_generator import generate_html_report
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            df_raw = generate_demo_data(output_path=Path(tmp) / "x.csv")
            html = generate_html_report(df_raw)
        assert "Rappi" in html
        assert "Uber Eats" in html
        assert "DiDi Food" in html

    def test_report_file_is_written_to_disk(self):
        """Smoke test: dataset loads, report is generated, file exists with expected content."""
        from generate_demo_data import generate_demo_data
        from report_generator import generate_html_report
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            csv_path    = Path(tmp) / "demo.csv"
            report_path = Path(tmp) / "report.html"
            df_raw = generate_demo_data(output_path=csv_path)
            assert csv_path.exists(), "Demo CSV was not created"
            generate_html_report(df_raw, report_path)
            assert report_path.exists(), "HTML report file was not created"
            content = report_path.read_text(encoding="utf-8")
            assert len(content) > 1000, "Report file appears empty"
            assert "Competitive Intelligence" in content, "Report missing expected title"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
