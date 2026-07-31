# EE Case Studies — LightRAG

<<<<<<< HEAD
Graph-based RAG pipeline over Equal Experts case studies, built with [LightRAG](https://github.com/HKUDS/LightRAG) and local LLMs via `llama.cpp` (`llama-server`). Everything runs on your machine — no API keys, no cloud services.

**Hard constraint:** fully local only. No Ollama, no cloud APIs. Every model runs through `llama.cpp` on Apple Silicon Metal.
=======
Graph-based RAG pipeline over Equal Experts case studies, built with [LightRAG](https://github.com/HKUDS/LightRAG) and **fully local** LLMs via llama.cpp. No API keys, no cloud services, no Ollama.
>>>>>>> a1cebcb (Refactor code structure for improved readability and maintainability)

## What This Does

- Scrapes all case studies from [equalexperts.com](https://www.equalexperts.com/case-studies/) (118 total)
- Indexes them into a LightRAG knowledge graph — entities, relationships, and vector embeddings
- Provides a query interface with 5 retrieval modes: local, global, hybrid, naive, mix
- Ships with an evaluation harness to measure retrieval quality across query types

## Tech Stack

<<<<<<< HEAD
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
=======
| Component       | Choice                                                                       |
| --------------- | ---------------------------------------------------------------------------- |
| RAG framework   | LightRAG (`lightrag-hku[api]`)                                               |
| LLM             | llama.cpp `LFM2.5-1.2B-Thinking` Q4_K_M (via OpenAI-compatible API on :8080) |
| Embeddings      | llama.cpp `bge-m3` Q8_0, 1024-dim (via OpenAI-compatible API on :8081)       |
| Reranker        | disabled (`RERANK_BINDING=null`) — LightRAG only wires cloud rerankers       |
| Scraper         | `requests` + `BeautifulSoup` + `lxml`                                        |
| Python          | 3.12+                                                                        |
| Package manager | `uv`                                                                         |
| Linter          | `ruff`                                                                       |
| Test runner     | `pytest`                                                                     |

## Architecture

LightRAG has no native llama.cpp binding, so it talks to two `llama-server`
instances over their OpenAI-compatible REST API using the `openai` binding.
Each server serves a single model:

```text
                    ┌──────────────────────────────┐
                    │   LightRAG  (lightrag-server) │  :9621
                    │   binding: openai             │
                    └──────┬───────────────┬────────┘
                           │ LLM_BINDING   │ EMBEDDING_BINDING
                           │ host :8080    │ host :8081
                    ┌──────▼───────┐ ┌──────▼───────┐
                    │ llama-server │ │ llama-server │
                    │ LFM2.5-1.2B  │ │ bge-m3       │
                    │ chat + extract│ │ embeddings   │
                    └──────────────┘ └──────────────┘
```
>>>>>>> a1cebcb (Refactor code structure for improved readability and maintainability)

## Prerequisites

1. **Python 3.12+** — check with `python3 --version`
2. **uv** — install with `pip install uv` or follow [the official guide](https://docs.astral.sh/uv/)
<<<<<<< HEAD
3. **llama.cpp** — installed via Homebrew: `brew install llama.cpp`
4. **Local GGUF models** on disk (see [Models](#models) below)
=======
3. **llama.cpp** — install with Homebrew: `brew install llama.cpp`
4. **Local models** (GGUF files already on this machine's HF hub cache):

   | Use       | Model                                | Size   | Params |
   | --------- | ------------------------------------ | ------ | ------ |
   | LLM       | `LiquidAI/LFM2.5-1.2B-Thinking-GGUF` | 697 MB | 1.2B   |
   | Embedding | `gpustack/bge-m3-GGUF`               | 605 MB | 110M   |

   The model paths live in `scripts/start_servers.sh` and resolve HF snapshot
   symlinks at runtime. Adjust `LLM_MODEL` / `EMBED_MODEL` there if you use
   different files.
>>>>>>> a1cebcb (Refactor code structure for improved readability and maintainability)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/TMFNK/ee-case-studies.git
cd ee-case-studies

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env
<<<<<<< HEAD
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
=======

# 4. Start the two llama.cpp servers (LLM :8080, bge-m3 :8081)
scripts/start_servers.sh            # background daemons; logs in logs/
scripts/start_servers.sh status     # check they're up
curl -s http://localhost:8080/v1/models
curl -s http://localhost:8081/v1/models

# 5. Start LightRAG server (web UI at http://localhost:9621)
uv run lightrag-server
>>>>>>> a1cebcb (Refactor code structure for improved readability and maintainability)

# 6. Scrape case studies
uv run python scripts/scrape_case_studies.py

# 7. Ingest into LightRAG
uv run python scripts/ingest.py

# 8. Query
uv run python scripts/query.py
```

<<<<<<< HEAD
## Models

All models are stored locally as GGUF files. The plan uses these:

| Role                     | Model                    | File                      | Size   | Path                                                                                                              |
| ------------------------ | ------------------------ | ------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------- |
| LLM (extract + generate) | LFM2.5-1.2B-Thinking     | `LFM2.5-1.2B-Thinking-Q4_K_M.gguf`  | 697 MB | `~/.cache/huggingface/hub/models--LiquidAI--LFM2.5-1.2B-Thinking-GGUF/snapshots/<rev>/...`   |
| Embedding                | bge-m3                   | `bge-m3-Q8_0.gguf`        | 605 MB | `~/.cache/huggingface/hub/models--gpustack--bge-m3-GGUF/snapshots/<rev>/...`                  |

Resolve the actual snapshot paths with `readlink -f` if needed.
=======
Stop the model servers with `scripts/start_servers.sh stop`.
>>>>>>> a1cebcb (Refactor code structure for improved readability and maintainability)

## Configuration

All configuration lives in `.env` (copied from `.env.example`). Key options:

### LLM

<<<<<<< HEAD
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
=======
| Variable              | Default                    | Description                           |
| --------------------- | -------------------------- | ------------------------------------- |
| `LLM_BINDING`         | `openai`                   | OpenAI-compatible backend             |
| `LLM_BINDING_HOST`    | `http://localhost:8080/v1` | llama-server LLM endpoint             |
| `LLM_MODEL`           | `lfm2.5-1.2b-thinking`     | Must match llama-server `--alias`     |
| `LLM_BINDING_API_KEY` | `sk-no-key-needed`         | Dummy key (see gotcha below)          |
| `EXTRACT_MODEL`       | —                          | Override model for entity extraction  |
| `QUERY_MODEL`         | —                          | Override model for query responses    |
| `KEYWORD_MODEL`       | —                          | Override model for keyword extraction |

### Embeddings

| Variable                    | Default                    | Description                       |
| --------------------------- | -------------------------- | --------------------------------- |
| `EMBEDDING_BINDING`         | `openai`                   | OpenAI-compatible backend         |
| `EMBEDDING_BINDING_HOST`    | `http://localhost:8081/v1` | llama-server embedding endpoint   |
| `EMBEDDING_MODEL`           | `bge-m3`                   | Must match llama-server `--alias` |
| `EMBEDDING_BINDING_API_KEY` | `sk-no-key-needed`         | Dummy key (see gotcha below)      |
| `EMBEDDING_DIM`             | `1024`                     | bge-m3 output dimension           |

### Reranker

Disabled by default (`RERANK_BINDING=null`). LightRAG only wires cloud
rerankers (cohere, jina, aliyun), so there is no local option.
>>>>>>> a1cebcb (Refactor code structure for improved readability and maintainability)

### Storage

Default is in-memory with local file persistence (`./rag_storage`). For
production, uncomment the PostgreSQL or Neo4j lines in `.env.example`.

### LightRAG Server

| Variable           | Default     | Description                                       |
| ------------------ | ----------- | ------------------------------------------------- |
| `LIGHTRAG_API_KEY` | (empty)     | API key for the LightRAG server                   |
| `HOST`             | `127.0.0.1` | `127.0.0.1` for local-only, `0.0.0.0` for network |
| `PORT`             | `9621`      | Server port                                       |

### Chunking & Ingest

| Variable                       | Default | Description                                             |
| ------------------------------ | ------- | ------------------------------------------------------- |
| `CHUNK_SIZE`                   | `1200`  | Token size per chunk                                    |
| `CHUNK_OVERLAP_SIZE`           | `100`   | Overlap between chunks                                  |
| `MAX_PARALLEL_INSERT`          | `4`     | Parallel extraction during ingest (main speed lever)    |
| `ENABLE_LLM_CACHE_FOR_EXTRACT` | `true`  | Cache entity/relation extraction for incremental reruns |

## The dummy API key gotcha

`llama-server` ignores `Authorization` unless started with `--key`, but
LightRAG's OpenAI client only sends a key if `LLM_BINDING_API_KEY` /
`EMBEDDING_BINDING_API_KEY` is set — otherwise it falls back to
`os.environ["OPENAI_API_KEY"]`, which raises `KeyError` on the first
LLM/embedding call. A non-empty placeholder (`sk-no-key-needed`) avoids that
crash.

## Entity Extraction (the knowledge-graph step)

During ingest, LightRAG splits each document into chunks and, **per chunk**,
calls the LLM once to extract entities and relationships as JSON:

```json
{
  "entities": [
    {
      "entity_name": "Equal Experts",
      "entity_type": "organisation",
      "description": "engineering consultancy"
    }
  ],
  "relationships": [
    {
      "src_id": "Equal Experts",
      "tgt_id": "IG Group",
      "description": "helped modernise",
      "keywords": "IG Group, Equal Experts"
    }
  ]
}
```

This output populates the NetworkX knowledge graph that powers the graph-based
query modes — `local`, `global`, `hybrid`, and `mix`. The `naive` mode bypasses
the graph entirely and uses plain vector similarity. If extraction output can't
be parsed, the graph stays empty and every graph-based mode returns
`[no-context]` while `naive` keeps working.

**Current status (verified 2026-07-31):** `LFM2.5-1.2B-Thinking` does not
follow the extraction JSON schema — it returns prose, so the graph ends up empty
(0 nodes / 0 edges). The model answers queries fine; it just can't be trusted
for the structured extraction step.

Check whether extraction worked after an ingest:

```bash
# node/edge counts (should be > 0)
python3 - <<'EOF'
import xml.etree.ElementTree as ET
t = ET.parse('rag_storage/graph_chunk_entity_relation.graphml')
ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}
print(len(t.getroot().findall('.//g:node', ns)), 'nodes,',
      len(t.getroot().findall('.//g:edge', ns)), 'edges')
EOF

# raw extraction output from the LLM (check it looks like JSON)
grep -o '"return": "[^"]*' rag_storage/kv_store_llm_response_cache.json | head
```

Fix options (in order of preference):

1. **Dedicated extraction model** — run `LFM2-350M-Extract` (purpose-built for
   extraction) as a third `llama-server` (e.g. :8082) and wire it in via the
   EXTRACT role:

   ```env
   EXTRACT_LLM_BINDING=openai
   EXTRACT_LLM_BINDING_HOST=http://localhost:8082/v1
   EXTRACT_LLM_MODEL=lfm2-350m-extract
   EXTRACT_LLM_BINDING_API_KEY=sk-no-key-needed
   ```

2. **Swap the main LLM** — point the LLM server at
   `WeiboAI.VibeThinker-1.5B` (1.07 GB, stronger instruction-following) and
   update `LLM_MODEL` to match its `--alias`.

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
│   ├── query.py                 # Query CLI
│   └── start_servers.sh         # Start/stop llama.cpp servers (LLM + bge-m3)
├── eval/
│   ├── cases.py                 # Eval cases (reused from assignment)
│   └── run_eval.py              # Evaluation runner
├── tests/                       # pytest tests
├── docs/                        # Documentation
<<<<<<< HEAD
│   └── EVALUATION.md            # Results comparison
├── .env.example                 # LightRAG config template (llama.cpp)
=======
├── logs/                        # llama-server logs and pid files (gitignored)
├── .env.example                 # LightRAG config template
>>>>>>> a1cebcb (Refactor code structure for improved readability and maintainability)
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