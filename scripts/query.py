"""Interactive CLI for querying the LightRAG knowledge base."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from lightrag import QueryParam

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from rag_setup import build_rag  # noqa: E402

MODES = ("local", "global", "hybrid", "naive", "mix")


async def run_once(query: str, mode: str, working_dir: Path | None) -> None:
    rag = build_rag(working_dir)
    await rag.initialize_storages()
    try:
        result = await rag.aquery(query, param=QueryParam(mode=mode))
        print(result)
    finally:
        await rag.finalize_storages()


async def run_repl(mode: str, working_dir: Path | None) -> None:
    rag = build_rag(working_dir)
    await rag.initialize_storages()
    print(f"LightRAG query CLI (mode={mode}). Commands: /mode <name>, /quit")
    try:
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line in {"/quit", "/exit", "quit", "exit"}:
                break
            if line.startswith("/mode "):
                new_mode = line.split(None, 1)[1].strip()
                if new_mode not in MODES:
                    print(f"unknown mode {new_mode!r}; choose from {', '.join(MODES)}")
                    continue
                mode = new_mode
                print(f"mode set to {mode}")
                continue
            result = await rag.aquery(line, param=QueryParam(mode=mode))
            print(result)
            print()
    finally:
        await rag.finalize_storages()


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the LightRAG knowledge base.")
    parser.add_argument("query", nargs="?", help="One-shot query (omit for REPL)")
    parser.add_argument(
        "--mode",
        default="mix",
        choices=MODES,
        help="Retrieval mode (default: mix)",
    )
    parser.add_argument(
        "--working-dir",
        default=None,
        help="LightRAG storage directory (default: ./rag_storage)",
    )
    args = parser.parse_args()
    working = Path(args.working_dir) if args.working_dir else None
    if args.query:
        asyncio.run(run_once(args.query, args.mode, working))
    else:
        asyncio.run(run_repl(args.mode, working))


if __name__ == "__main__":
    main()
