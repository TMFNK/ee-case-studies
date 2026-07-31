# EE Case Studies — LightRAG

Graph-based RAG pipeline over Equal Experts case studies, built with [LightRAG](https://github.com/HKUDS/LightRAG) and local LLMs via `llama.cpp` (`llama-server`). Everything runs on your machine — no API keys, no cloud services.

**Hard constraint:** fully local only. No Ollama, no cloud APIs. Every model runs through `llama.cpp` on Apple Silicon Metal.

## What This Does

- Scrapes all case studies from [equalexperts.com](https://www.equalexperts.com/case-studies/) (118 total)
- Indexes them into a LightRAG knowledge graph — entities, relationships, and vector embeddings
- Provides a query interface with 5 retrieval modes: local, global, hybrid, naive, mix
- Ships with an evaluation harness to measure retrieval quality across query types

## Tech Stack

| Component       | Choice                                              |
| --------------- | --------------------------------------------------- |
| RAG framework   | LightRAG (`lightrag-hku[api]`)                      |
| LLM             | `llama.cpp` `LFM2.5-1.2B-Thinking` (Q4_K_M)        |
| Embeddings      | `llama.cpp` `bge-m3` (Q8_0, 1024-dim)               |
| Scraper         | `requests` + `BeautifulSoup` + `lxml`               |
| Python          | 3.12+                                               |
| Package manager | `uv`                                                |
| Linter          | `ruff`                                              |
| Test runner     | `pytest`                                            |

## Prerequisites

1. **Python 3.12+** — check with `python3 --version`
2. **uv** — install with `pip install uv` or follow [the official guide](https://docs.astral.sh/uv/)
3. **llama.cpp** — installed via Homebrew: `brew install llama.cpp`
4. **Local GGUF models** on disk (see [Models](#models) below)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/TMFNK/ee-case-studies.git
cd ee-case-studies

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env if you need different model paths or ports

# 4. Start the two llama.cpp servers (one terminal each, or background)
# LLM server on port 8080:
llama-server \
  --model /path/to/LFM2.5-1.2B-Thinking-Q4_K_M.gguf \
  --model-alias lfm2.5-1.2b-thinking \
  --port 8080 -ngl 999

# Embedding server on port 8081:
llama-server \
  --model /path/to/bge-m3-Q8_0.gguf \
  --model-alias bge-m3 \
  --embedding --pooling mean \
  --port 8081 -ngl 999

# 5. Verify both servers respond
curl http://localhost:8080/v1/models
curl http://localhost:8081/v1/models

# 6. Scrape case studies
uv run python scripts/scrape_case_studies.py

# 7. Ingest into LightRAG
uv run python scripts/ingest.py

# 8. Query
uv run python scripts/query.py
# Or open the LightRAG web UI at http://localhost:9621
```

## Models

All models are stored locally as GGUF files. The plan uses these:

| Role                     | Model                    | File                      | Size   | Path                                                                                                              |
| ------------------------ | ------------------------ | ------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------- |
| LLM (extract + generate) | LFM2.5-1.2B-Thinking     | `LFM2.5-1.2B-Thinking-Q4_K_M.gguf`  | 697 MB | `~/.cache/huggingface/hub/models--LiquidAI--LFM2.5-1.2B-Thinking-GGUF/snapshots/<rev>/...`   |
| Embedding                | bge-m3                   | `bge-m3-Q8_0.gguf`        | 605 MB | `~/.cache/huggingface/hub/models--gpustack--bge-m3-GGUF/snapshots/<rev>/...`                  |

Resolve the actual snapshot paths with `readlink -f` if needed.

## Configuration

All configuration lives in `.env` (copied from `.env.example`). Key options:

### LLM

| Variable               | Default                        | Description                            |
| ---------------------- | ------------------------------ | -------------------------------------- |
| `LLM_BINDING`          | `openai`                       | LLM backend (use `openai` for llama.cpp) |
| `LLM_BINDING_HOST`     | `http://localhost:8080/v1`      | `llama-server` LLM URL                 |
| `LLM_MODEL`            | `lfm2.5-1.2b-thinking`         | Model name (must match `--model-alias`) |
| `LLM_BINDING_API_KEY`  | `sk-no-key-needed`             | Dummy key (required by LightRAG, ignored by llama.cpp) |

### Embeddings

| Variable                   | Default                        | Description                                |
| -------------------------- | ------------------------------ | ------------------------------------------ |
| `EMBEDDING_BINDING`        | `openai`                       | Embedding backend                          |
| `EMBEDDING_BINDING_HOST`   | `http://localhost:8081/v1`      | `llama-server` embedding URL               |
| `EMBEDDING_MODEL`          | `bge-m3`                       | Embedding model name                       |
| `EMBEDDING_BINDING_API_KEY`| `sk-no-key-needed`             | Dummy key                                  |
| `EMBEDDING_DIM`            | `1024`                         | Embedding dimensionality (bge-m3 output)   |

### Storage

Default is in-memory with local file persistence. For production, uncomment the PostgreSQL or Neo4j lines and configure connection details.

### LightRAG Server

| Variable           | Default     | Description                                       |
| ------------------ | ----------- | ------------------------------------------------- |
| `LIGHTRAG_API_KEY` | (empty)     | API key for the LightRAG server                   |
| `HOST`             | `127.0.0.1` | `127.0.0.1` for local-only, `0.0.0.0` for network |
| `PORT`             | `9621`      | Server port                                       |

### Chunking

| Variable        | Default     | Description                                              |
| --------------- | ----------- | -------------------------------------------------------- |
| `CHUNK_SIZE`    | `1200`      | Token size per chunk                                     |
| `CHUNK_OVERLAP` | `100`       | Overlap between chunks                                   |
| `CHUNK_METHOD`  | `paragraph` | Strategy: `fixed`, `recursive`, `vector`, or `paragraph` |

### Ingest Tuning

| Variable                       | Default | Description                                                        |
| ------------------------------ | ------- | ------------------------------------------------------------------ |
| `MAX_PARALLEL_INSERT`          | `4`     | Parallel extraction workers (main speed lever for local LLMs)      |
| `ENABLE_LLM_CACHE_FOR_EXTRACT` | `true`  | Cache extraction results so re-runs are incremental and fast       |

## Scraper

```bash
# Full scrape (118 case studies)
uv run python scripts/scrape_case_studies.py

# Test on a subset
uv run python scripts/scrape_case_studies.py --limit 5

# Custom concurrency
uv run python scripts/scrape_case_studies.py --concurrency 4

# Custom output directory
uv run python scripts/scrape_case_studies.py --output my_data
```

Output:
- `data/case_studies.jsonl` — incremental, one JSON object per line
- `data/case_studies.json` — final array sorted by sitemap order
- `data/scrape-errors.log` — logs of any URLs that failed after retries

## Retrieval Modes

| Mode     | What it does                                     | Best for                                        |
| -------- | ------------------------------------------------ | ----------------------------------------------- |
| `local`  | Entity-centric lookup within the knowledge graph | Specific questions about a client or technology |
| `global` | Broad graph traversal across all case studies    | Cross-case comparisons and themes               |
| `hybrid` | Combines local + global                          | Questions that need both detail and breadth     |
| `naive`  | Standard vector similarity (no graph)            | Baseline comparison                             |
| `mix`    | Blends graph and vector retrieval                | General-purpose queries                         |

## Project Structure

```tree
ee-case-studies/
├── data/
│   ├── case_studies.json        # Scraped case studies (118)
│   └── case_studies.jsonl       # Incremental scrape backup
├── scripts/
│   ├── scrape_case_studies.py   # Concurrent scraper
│   ├── ingest.py                # LightRAG ingestion
│   └── query.py                 # Query CLI
├── eval/
│   ├── cases.py                 # Eval cases (reused from assignment)
│   └── run_eval.py              # Evaluation runner
├── tests/                       # pytest tests
├── docs/                        # Documentation
│   └── EVALUATION.md            # Results comparison
├── .env.example                 # LightRAG config template (llama.cpp)
├── pyproject.toml               # Project metadata and dependencies
└── README.md
```

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format --check .
```

## Evaluation

The `eval/` directory contains a test harness for measuring retrieval quality:

1. Define eval cases in `eval/cases.py` — each case has a query, expected entities, and expected source case studies
2. Run `uv run python eval/run_eval.py` to execute all cases across all retrieval modes
3. Results show precision, recall, and F1 per mode

## License

AGPL-3.0 — see [LICENSE](LICENSE).