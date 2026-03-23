"""
main.py -- Main entry point for the Competitive Intelligence scraping pipeline.

Usage (from project ROOT):
  python -m app.main --dry-run
  python -m app.main --platforms rappi uber didi
  python -m app.main --platforms rappi --limit 3 --no-headless
  python -m app.main --analyze

  # Or from inside app/:
  cd app && python main.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

# -- Path resolution ----------------------------------------------------
# BASE_DIR = project root (parent of app/).
# Works regardless of cwd: from root, from app/, or via python -m app.main
BASE_DIR     = Path(__file__).resolve().parent.parent
SCRAPERS_DIR = BASE_DIR / "scrapers"
ANALYSIS_DIR = BASE_DIR / "analysis"

for _p in [str(SCRAPERS_DIR), str(ANALYSIS_DIR), str(BASE_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import (
    RUN_ID, OUTPUT_CSV, LATEST_CSV, ADDRESSES_FILE,
    PRODUCT_MAP_FILE, OUTPUT_COLUMNS, LOGS_DIR, PROCESSED_DIR,
)
from models import ScrapeSession, PriceObservation

# -- Logging ------------------------------------------------------------
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / f"main_{RUN_ID}.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# -- Scraper factory ----------------------------------------------------
def get_scraper(platform: str, run_id: str, headless: bool = True):
    if platform == "rappi":
        from rappi_scraper import RappiScraper
        return RappiScraper(run_id=run_id, headless=headless)
    elif platform == "uber":
        from uber_scraper import UberEatsScraper
        return UberEatsScraper(run_id=run_id, headless=headless)
    elif platform == "didi":
        from didi_scraper import DidiScraper
        return DidiScraper(run_id=run_id, headless=headless)
    else:
        raise ValueError(f"Unknown platform: {platform}")


# -- CSV writer ---------------------------------------------------------
def write_observation(obs: PriceObservation, output_file: Path, write_header: bool):
    with open(output_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow({k: obs.to_dict().get(k, "") for k in OUTPUT_COLUMNS})


# -- Platform scrape loop -----------------------------------------------
async def scrape_platform(
    platform: str,
    addresses: list,
    chain: str,
    product_keys: list,
    run_id: str,
    output_file: Path,
    headless: bool,
    session: ScrapeSession,
) -> int:
    logger.info(f"[{platform}] Starting: {len(addresses)} addresses")
    scraper    = get_scraper(platform, run_id, headless)
    obs_count  = 0
    first_write = not output_file.exists()

    try:
        await scraper.start()
        for i, address_row in enumerate(addresses, 1):
            addr_id = address_row.get("address_id", f"addr_{i:02d}")
            logger.info(f"[{platform}] {i}/{len(addresses)}: {addr_id}")

            observations = await scraper.scrape_address(
                address_row=address_row, chain=chain, product_keys=product_keys
            )
            for obs in observations:
                write_observation(obs, output_file, write_header=(first_write and obs_count == 0))
                first_write = False
                obs_count += 1
                session.observations += 1
                if obs.status == "success":
                    session.success_count += 1
                elif obs.status == "blocked":
                    session.blocked_count += 1
                else:
                    session.error_count += 1

            session.addresses_done += 1

    except Exception as e:
        logger.error(f"[{platform}] Failed: {e}", exc_info=True)
    finally:
        await scraper.stop()

    logger.info(f"[{platform}] Done: {obs_count} observations")
    return obs_count


# -- Dry run ------------------------------------------------------------
def dry_run(platforms: list, addresses: list, chain: str, products: list):
    logger.info("=" * 55)
    logger.info("DRY RUN -- No scraping will be performed")
    logger.info("=" * 55)
    logger.info(f"  Run ID    : {RUN_ID}")
    logger.info(f"  Platforms : {platforms}")
    logger.info(f"  Addresses : {len(addresses)}")
    logger.info(f"  Chain     : {chain}")
    logger.info(f"  Products  : {products}")
    logger.info(f"  Output    : {OUTPUT_CSV}")
    est = len(platforms) * len(addresses) * len(products)
    logger.info(f"  Est. obs  : {len(platforms)} x {len(addresses)} x {len(products)} = {est}")
    logger.info("  Demo data : python analysis/generate_demo_data.py")
    logger.info("  Dashboard : streamlit run app/dashboard.py")
    logger.info("=" * 55)
    logger.info("Dry run complete -- no errors")


# -- Analysis trigger ---------------------------------------------------
def run_analysis(csv_path: Path):
    if not csv_path.exists():
        logger.error(f"No data file found: {csv_path}")
        logger.info("Run: python analysis/generate_demo_data.py")
        return
    logger.info(f"Running analysis on: {csv_path}")
    from normalize        import normalize_dataset
    from insights         import generate_insights
    from report_generator import generate_html_report

    df_raw   = pd.read_csv(csv_path)
    df       = normalize_dataset(df_raw)
    insights = generate_insights(df)
    for ins in insights:
        logger.info(f"\n  #{ins['id']} [{ins['severity'].upper()}] {ins['title']}")
        logger.info(f"  Finding: {ins['finding'][:120]}...")

    # Generate HTML report automatically
    reports_dir = BASE_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"competitive_intelligence_report_{ts}.html"
    generate_html_report(df_raw, report_path)
    generate_html_report(df_raw, reports_dir / "competitive_intelligence_report_latest.html")
    logger.info(f"HTML report saved: {report_path.name}")


# -- Main ---------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(
        description="Rappi Competitive Intelligence Scraper",
        epilog=(
            "Examples:\n"
            "  python -m app.main --dry-run\n"
            "  python -m app.main --platforms rappi uber didi\n"
            "  python -m app.main --analyze\n"
        ),
    )
    parser.add_argument("--platforms",   nargs="+", default=["rappi","uber","didi"],
                        choices=["rappi","uber","didi"])
    parser.add_argument("--addresses",   type=str, default=str(ADDRESSES_FILE))
    parser.add_argument("--chain",       type=str, default="mcdonalds")
    parser.add_argument("--products",    nargs="+", default=None)
    parser.add_argument("--limit",       type=int, default=None)
    parser.add_argument("--headless",    action="store_true", default=True)
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--analyze",     action="store_true")
    args = parser.parse_args()

    headless = not args.no_headless

    addr_path = Path(args.addresses)
    if not addr_path.exists():
        logger.error(f"Addresses file not found: {addr_path}")
        sys.exit(1)

    addresses = list(csv.DictReader(open(addr_path, encoding="utf-8")))
    if args.limit:
        addresses = addresses[:args.limit]

    with open(PRODUCT_MAP_FILE, encoding="utf-8") as f:
        product_map = json.load(f)
    product_keys = args.products or product_map.get("priority_products", [])

    if args.dry_run:
        dry_run(args.platforms, addresses, args.chain, product_keys)
        return

    if args.analyze:
        run_analysis(LATEST_CSV if LATEST_CSV.exists() else OUTPUT_CSV)
        return

    # Full scraping
    session = ScrapeSession(run_id=RUN_ID, platforms=args.platforms,
                             addresses_total=len(addresses)*len(args.platforms))
    total_obs  = 0
    start_time = time.time()

    for platform in args.platforms:
        total_obs += await scrape_platform(
            platform=platform, addresses=addresses, chain=args.chain,
            product_keys=product_keys, run_id=RUN_ID, output_file=OUTPUT_CSV,
            headless=headless, session=session,
        )

    elapsed = time.time() - start_time
    if OUTPUT_CSV.exists():
        shutil.copy2(OUTPUT_CSV, LATEST_CSV)

    summary = session.summary()
    with open(PROCESSED_DIR / f"session_{RUN_ID}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"COMPLETE -- {total_obs} obs | {summary['success_rate']:.0%} success | {elapsed/60:.1f} min")


if __name__ == "__main__":
    asyncio.run(main())
