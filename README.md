# EE Case Studies — LightRAG

Graph-based RAG pipeline over Equal Experts case studies, built with [LightRAG](https://github.com/HKUDS/LightRAG) and local LLMs via Ollama. Everything runs on your machine — no API keys, no cloud services.

## What This Does

- Scrapes all case studies from [equalexperts.com/case-studies](https://www.equalexperts.com/case-studies/) (118 total)
- Indexes them into a LightRAG knowledge graph — entities, relationships, and vector embeddings
- Provides a query interface with 5 retrieval modes: local, global, hybrid, naive, mix
- Ships with an evaluation harness to measure retrieval quality across query types

## Tech Stack

| Component       | Choice                                |
| --------------- | ------------------------------------- |
| RAG framework   | LightRAG (`lightrag-hku[api]`)        |
| LLM             | Ollama `llama3.2`                     |
| Embeddings      | Ollama `nomic-embed-text` (768-dim)   |
| Scraper         | `requests` + `BeautifulSoup` + `lxml` |
| Python          | 3.12+                                 |
| Package manager | `uv`                                  |
| Linter          | `ruff`                                |
| Test runner     | `pytest`                              |

## Prerequisites

1. **Python 3.12+** — check with `python3 --version`
2. **uv** — install with `pip install uv` or follow [the official guide](https://docs.astral.sh/uv/)
3. **Ollama** — install from [ollama.com](https://ollama.com), then pull the models:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/TMFNK/ee-case-studies.git
cd ee-case-studies

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env if you need different models or ports

# 4. Scrape case studies
uv run python scripts/scrape_case_studies.py

# 5. Ingest into LightRAG
uv run python scripts/ingest.py

# 6. Query
uv run python scripts/query.py
# Or open the LightRAG web UI at http://localhost:9621
```

## Configuration

All configuration lives in `.env` (copied from `.env.example`). Key options:

### LLM

| Variable           | Default                  | Description                            |
| ------------------ | ------------------------ | -------------------------------------- |
| `LLM_BINDING`      | `ollama`                 | LLM backend                            |
| `LLM_BINDING_HOST` | `http://localhost:11434` | Ollama server URL                      |
| `LLM_MODEL`        | `llama3.2`               | Model used for extraction and querying |
| `EXTRACT_MODEL`    | —                        | Override model for entity extraction   |
| `QUERY_MODEL`      | —                        | Override model for query responses     |
| `KEYWORD_MODEL`    | —                        | Override model for keyword extraction  |

### Embeddings

| Variable                 | Default                  | Description              |
| ------------------------ | ------------------------ | ------------------------ |
| `EMBEDDING_BINDING`      | `ollama`                 | Embedding backend        |
| `EMBEDDING_BINDING_HOST` | `http://localhost:11434` | Ollama server URL        |
| `EMBEDDING_MODEL`        | `nomic-embed-text`       | Embedding model          |
| `EMBEDDING_DIM`          | `768`                    | Embedding dimensionality |

### Reranker (optional)

Uncomment the `RERANK_BINDING` and `RERANK_MODEL` lines to enable `bge-reranker-v2-m3` for improved mixed-query quality.

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
│   └── case_studies.json        # Scraped case studies
├── scripts/
│   ├── scrape_case_studies.py   # Scraper
│   ├── ingest.py                # LightRAG ingestion
│   └── query.py                 # Query CLI
├── eval/
│   ├── cases.py                 # Eval cases
│   └── run_eval.py              # Evaluation runner
├── tests/                       # pytest tests
├── docs/                        # Documentation
├── .env.example                 # LightRAG config template
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
