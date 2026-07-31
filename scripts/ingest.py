"""Ingest scraped Equal Experts case studies into LightRAG."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from rag_setup import build_rag  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_case_studies(path: Path, limit: int | None) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"expected a JSON array in {path}")
    if limit is not None:
        data = data[:limit]
    return data


def format_document(case: dict) -> str:
    categories = ", ".join(case.get("categories") or []) or "(none)"
    date = case.get("date") or "(unknown)"
    return (
        f"Title: {case['title']}\n"
        f"URL: {case['url']}\n"
        f"Date: {date}\n"
        f"Categories: {categories}\n\n"
        f"{case['content']}"
    )


async def ingest(data_path: Path, limit: int | None, working_dir: Path | None) -> None:
    cases = load_case_studies(data_path, limit)
    if not cases:
        raise SystemExit("no case studies to ingest")

    rag = build_rag(working_dir)
    await rag.initialize_storages()
    try:
        texts = [format_document(c) for c in cases]
        ids = [f"case-{c['id']}" for c in cases]
        file_paths = [c["url"] for c in cases]
        logger.info("inserting %d case studies…", len(texts))
        track_id = await rag.ainsert(texts, ids=ids, file_paths=file_paths)
        logger.info("ingest finished (track_id=%s)", track_id)
    finally:
        await rag.finalize_storages()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest case studies into LightRAG.")
    parser.add_argument(
        "--data",
        default=str(ROOT / "data" / "case_studies.json"),
        help="Path to case_studies.json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ingest only the first N case studies (smoke test)",
    )
    parser.add_argument(
        "--working-dir",
        default=None,
        help="LightRAG storage directory (default: ./rag_storage)",
    )
    args = parser.parse_args()
    asyncio.run(
        ingest(
            Path(args.data),
            args.limit,
            Path(args.working_dir) if args.working_dir else None,
        )
    )


if __name__ == "__main__":
    main()
