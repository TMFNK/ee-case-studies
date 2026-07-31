"""
Equal Experts Case Studies — Concurrent Scraper

DESCRIPTION:
1. Fetches the sitemap from equalexperts.com to discover all 118 case study URLs
2. Downloads each page concurrently with retries and polite throttling
3. Parses each page with BeautifulSoup (lxml) to extract title, content, date, and categories
4. Writes results incrementally to a JSONL file (crash-safe partial progress)
5. Assembles the final sorted JSON array at the end

PREREQUISITES:
1. Python 3.12+ must be installed
2. uv package manager must be installed

SETUP:
1. Install uv: `pip install uv` (or follow official instructions)
2. cd ee-case-studies
3. Install dependencies: `uv sync`

FILE REQUIREMENTS:
- No input files required
- Sitemap URL: https://www.equalexperts.com/case_study-sitemap.xml
- Case study pages must be server-rendered (no JavaScript needed)

USAGE:
    uv run python scripts/scrape_case_studies.py
    uv run python scripts/scrape_case_studies.py --limit 5    # test on a subset
    uv run python scripts/scrape_case_studies.py --concurrency 4  # slower, more polite
    uv run python scripts/scrape_case_studies.py --output my_data/cases.json  # custom output

OUTPUT:
- data/case_studies.jsonl — incremental, one JSON object per line
- data/case_studies.json — final array sorted by sitemap order
- data/scrape-errors.log — logs of any URLs that failed after retries

DEPENDENCIES:
- requests>=2.32.0
- beautifulsoup4>=4.12.0
- lxml>=5.0.0
- tqdm>=4.66.0

TROUBLESHOOTING:
- If you get SSL errors, check your network connection
- If a page fails to parse, check scrape-errors.log
- The scraper is designed to be idempotent — re-running it overwrites output files
- Rate limiting: if you get 429 responses, lower concurrency with --concurrency 2
"""

import argparse
import json
import logging
import os
import random
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tqdm import tqdm

# ── Constants ──────────────────────────────────────────────────────────────────

SITEMAP_URL = "https://www.equalexperts.com/case_study-sitemap.xml"
DEFAULT_CONCURRENCY = 8
DEFAULT_OUTPUT_DIR = "data"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Namespace map for parsing the sitemap XML
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# ── Logging Setup ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Sitemap Parsing ────────────────────────────────────────────────────────────


def fetch_sitemap_urls(sitemap_url: str, session: requests.Session) -> list[str]:
    """Fetch the sitemap XML and return all case study URLs in order."""
    logger.info("Fetching sitemap from %s", sitemap_url)
    resp = session.get(sitemap_url, timeout=30)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    urls = []
    for url_elem in root.findall(".//sm:url/sm:loc", SITEMAP_NS):
        loc_text = url_elem.text.strip() if url_elem.text else ""
        if loc_text:
            urls.append(loc_text)

    logger.info("Found %d case study URLs in sitemap", len(urls))
    return urls


# ── Page Parsing ────────────────────────────────────────────────────────────────


def parse_case_study(html: str, url: str) -> Optional[dict]:
    """Parse a case study page's HTML into a structured dict.

    Uses targeted CSS selectors with fallbacks for different WordPress
    theme variations.
    """
    soup = BeautifulSoup(html, "lxml")

    # ── Title ──
    title = ""
    for selector in ["h1", "h1.entry-title", "h1.cs-title", ".entry-title"]:
        tag = soup.select_one(selector)
        if tag and tag.get_text(strip=True):
            title = tag.get_text(strip=True)
            break

    # ── Content (body text) ──
    content = ""
    for selector in [
        ".entry-content",
        ".content-area",
        "article",
        "main",
        ".post-content",
    ]:
        tag = soup.select_one(selector)
        if tag:
            # Remove script, style, nav, and other non-content elements
            for unwanted in tag.select("script, style, nav, .nav-links, .post-navigation"):
                unwanted.decompose()
            content = tag.get_text(separator="\n", strip=True)
            if len(content) > 50:  # Sanity check: at least 50 chars of real content
                break

    # Fallback: grab everything inside <body>
    if not content or len(content) < 50:
        body = soup.find("body")
        if body:
            for unwanted in body.select("script, style, nav"):
                unwanted.decompose()
            content = body.get_text(separator="\n", strip=True)

    # ── Date ──
    date = ""
    # Try <meta> tag with article:published_time first
    meta_tag = soup.find("meta", attrs={"property": "article:published_time"})
    if meta_tag and meta_tag.get("content"):
        date = meta_tag["content"][:10]  # YYYY-MM-DD
    else:
        # Try <time> tag
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            date = time_tag["datetime"][:10]
        else:
            # Try .entry-date class
            date_tag = soup.select_one(".entry-date")
            if date_tag and date_tag.get("datetime"):
                date = date_tag["datetime"][:10]

    # ── Categories / Tags ──
    categories: list[str] = []
    for selector in [".cat-links a", ".post-tags a", ".category-links a", ".tags-links a"]:
        tags = soup.select(selector)
        for tag in tags:
            text = tag.get_text(strip=True)
            if text and text not in categories:
                categories.append(text)
        if categories:
            break

    # Validate: we need at least a title and some content
    if not title or not content:
        logger.warning("Failed to parse %s — title=%r, content_len=%d", url, title, len(content))
        return None

    return {
        "title": title,
        "url": url,
        "content": content,
        "date": date,
        "categories": categories,
    }


# ── Fetch + Parse One URL ──────────────────────────────────────────────────────


def fetch_and_parse(
    url: str,
    case_id: int,
    session: requests.Session,
) -> tuple[int, Optional[dict]]:
    """Fetch a single case study URL and parse it.

    Returns (case_id, parsed_dict_or_None) so the caller can track order.
    Adds a small random jitter between requests to stay polite.
    """
    time.sleep(random.uniform(0.1, 0.3))  # Polite jitter
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        parsed = parse_case_study(resp.text, url)
        return case_id, parsed
    except requests.RequestException as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return case_id, None


# ── Main Scraper ────────────────────────────────────────────────────────────────


def scrape(
    sitemap_url: str = SITEMAP_URL,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    concurrency: int = DEFAULT_CONCURRENCY,
    limit: Optional[int] = None,
) -> None:
    """Run the full scrape pipeline: sitemap → concurrent fetch → parse → write."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    jsonl_path = output_path / "case_studies.jsonl"
    json_path = output_path / "case_studies.json"
    error_log_path = output_path / "scrape-errors.log"

    # Set up a session with connection pooling and retries
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(
        pool_connections=concurrency,
        pool_maxsize=concurrency + 2,
        max_retries=retry_strategy,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Step 1: Fetch sitemap
    all_urls = fetch_sitemap_urls(sitemap_url, session)
    if limit is not None:
        all_urls = all_urls[:limit]
        logger.info("Limited to first %d URLs", limit)

    # Step 2: Fetch and parse concurrently
    results: list[Optional[dict]] = [None] * len(all_urls)
    error_count = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(fetch_and_parse, url, idx, session): idx
            for idx, url in enumerate(all_urls)
        }

        with tqdm(total=len(all_urls), desc="Scraping", unit="page") as pbar:
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    _, parsed = future.result()
                    results[idx] = parsed
                    if parsed is not None:
                        # Write incrementally to JSONL
                        with open(jsonl_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps(parsed, ensure_ascii=False) + "\n")
                    else:
                        error_count += 1
                        with open(error_log_path, "a", encoding="utf-8") as f:
                            f.write(f"{all_urls[idx]}\n")
                except Exception as exc:
                    logger.error("Unexpected error for URL %s: %s", all_urls[idx], exc)
                    error_count += 1
                    with open(error_log_path, "a", encoding="utf-8") as f:
                        f.write(f"{all_urls[idx]} — {exc}\n")
                pbar.update(1)

    # Step 3: Assemble final JSON array (sorted by sitemap order)
    case_studies = []
    for idx, parsed in enumerate(results):
        if parsed is not None:
            # Add sequential id matching sitemap order
            parsed["id"] = len(case_studies) + 1
            case_studies.append(parsed)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(case_studies, f, ensure_ascii=False, indent=2)

    # Summary
    summary = (
        f"\n{'=' * 50}\n"
        f"Scrape complete\n"
        f"  Total URLs:     {len(all_urls)}\n"
        f"  Successfully:   {len(case_studies)}\n"
        f"  Failed:         {error_count}\n"
        f"  JSONL output:   {jsonl_path}\n"
        f"  JSON output:    {json_path}\n"
        f"  Error log:      {error_log_path}\n"
        f"{'=' * 50}"
    )
    print(summary)


# ── CLI Entry Point ────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Equal Experts case studies from the sitemap.",
    )
    parser.add_argument(
        "--sitemap-url",
        default=SITEMAP_URL,
        help=f"Sitemap URL (default: {SITEMAP_URL})",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Concurrent fetches (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit to first N URLs (useful for testing)",
    )
    args = parser.parse_args()

    scrape(
        sitemap_url=args.sitemap_url,
        output_dir=args.output,
        concurrency=args.concurrency,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()