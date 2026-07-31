# EE Case Studies / LightRAG

Graph-based RAG over Equal Experts case studies, built with
[LightRAG](https://github.com/HKUDS/LightRAG) and local models via `llama.cpp`
(`llama-server`). No API keys and no cloud calls: every model runs through
`llama.cpp` on Apple Silicon Metal.

Fully local only without Ollama. A full ingest of all 118 case studies lands around
**~700 nodes / ~400 edges** in `./rag_storage`.

## What this does

- Scrapes case studies from [equalexperts.com](https://www.equalexperts.com/case-studies/)
- Builds a LightRAG knowledge graph (entities, relationships, embeddings)
- Answers questions in five modes: local, global, hybrid, naive, mix
- Ships an `eval/` runner for retrieval quality checks

## Tech stack

| Component       | Choice                                                           |
| --------------- | ---------------------------------------------------------------- |
| RAG framework   | LightRAG (`lightrag-hku[api]`)                                   |
| LLM (query)     | llama.cpp `LFM2.5-1.2B-Thinking` Q4_K_M on :8080                 |
| LLM (extract)   | llama.cpp `LFM2-350M-Extract` Q4_K_M on :8082                    |
| Embeddings      | llama.cpp `bge-m3` Q8_0, 1024-dim on :8081                       |
| Reranker        | off (`RERANK_BINDING=null`; LightRAG only wires cloud rerankers) |
| Scraper         | `requests` + `BeautifulSoup` + `lxml`                            |
| Python          | 3.12+                                                            |
| Package manager | `uv`                                                             |
| Linter          | `ruff`                                                           |
| Tests           | `pytest`                                                         |

## Architecture

LightRAG has no native llama.cpp binding, so it talks to `llama-server` over the
OpenAI-compatible REST API (`openai` binding).

On **8GB Apple Silicon**, do not run all three servers at once. They OOM under
load. Use the phased modes in `scripts/start_servers.sh`:

| Mode     | Servers                     | Use for             |
| -------- | --------------------------- | ------------------- |
| `ingest` | extract :8082 + embed :8081 | `scripts/ingest.py` |
| `query`  | LLM :8080 + embed :8081     | `scripts/query.py`  |
| `all`    | all three (16GB+)           | web UI / demos      |

```text
                    ┌──────────────────────────────────┐
                    │   LightRAG  (CLI or lightrag-server)
                    │   binding: openai                │
                    └───┬──────────┬──────────────┬────┘
                        │ query    │ extract      │ embed
                        │ :8080    │ :8082        │ :8081
                 ┌──────▼──────┐ ┌─▼──────────┐ ┌─▼──────────┐
                 │ llama-server│ │llama-server│ │llama-server│
                 │ LFM2.5-1.2B │ │LFM2-350M   │ │ bge-m3     │
                 │ Thinking    │ │ Extract    │ │ embeddings │
                 │ ctx 4096    │ │ ctx 16384  │ │ ctx/ub 2048│
                 └─────────────┘ └────────────┘ └────────────┘
```

`scripts/rag_setup.py` builds LightRAG from `.env`. During ingest-only runs, if
query LLM (:8080) is down it falls back to the extract server as the base LLM
so indexing can continue.

## Prerequisites

1. **Python 3.12+** (`python3 --version`)
2. **uv** ([install guide](https://docs.astral.sh/uv/) or `pip install uv`)
3. **llama.cpp** (`brew install llama.cpp`)
4. Local GGUF models in the HF hub cache:

   | Use       | Model                                | Size   | Params |
   | --------- | ------------------------------------ | ------ | ------ |
   | LLM       | `LiquidAI/LFM2.5-1.2B-Thinking-GGUF` | 697 MB | 1.2B   |
   | Extract   | `LiquidAI/LFM2-350M-Extract-GGUF`    | 219 MB | 350M   |
   | Embedding | `gpustack/bge-m3-GGUF`               | 605 MB | 110M   |

   Paths live in `scripts/start_servers.sh` and resolve HF snapshot symlinks at
   runtime. Override with `LLM_MODEL` / `EXTRACT_MODEL` / `EMBED_MODEL` if needed.

## Quick start

```bash
# 1. Clone
git clone https://github.com/TMFNK/ee-case-studies.git
cd ee-case-studies

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env

# 4. Scrape (skip if data/case_studies.json already exists)
uv run python scripts/scrape_case_studies.py

# 5. Ingest (extract + embed only; fits 8GB)
scripts/start_servers.sh start ingest
scripts/start_servers.sh status
uv run python scripts/ingest.py
# Smoke test:  uv run python scripts/ingest.py --limit 1

# 6. Query (swap to query LLM + embed)
scripts/start_servers.sh start query
uv run python scripts/query.py
# One-shot:  uv run python scripts/query.py "How did EE help HMRC?" --mode mix

# Optional web UI (mode=all on 16GB+, or query mode carefully)
# uv run lightrag-server   # http://127.0.0.1:9621
```

Stop servers with `scripts/start_servers.sh stop`.

Use `127.0.0.1`, not `localhost`. Servers bind IPv4 only; `localhost` may hit
`::1` first and look down.

## Resume ingest (keep `rag_storage`)

LightRAG tracks per-document status under `rag_storage/`. Re-run ingest without
deleting that directory to skip completed docs and retry failed ones:

```bash
scripts/start_servers.sh start ingest
uv run python scripts/ingest.py
```

Wipe only for a full rebuild:

```bash
rm -rf rag_storage
```

## Models

| Role      | Model                | File                               | Size   | Port | Server flags (`start_servers.sh`)                             |
| --------- | -------------------- | ---------------------------------- | ------ | ---- | ------------------------------------------------------------- |
| Query     | LFM2.5-1.2B-Thinking | `LFM2.5-1.2B-Thinking-Q4_K_M.gguf` | 697 MB | 8080 | `--ctx-size 4096`                                             |
| Extract   | LFM2-350M-Extract    | `LFM2-350M-Extract-Q4_K_M.gguf`    | 219 MB | 8082 | `--ctx-size 16384`                                            |
| Embedding | bge-m3               | `bge-m3-Q8_0.gguf`                 | 605 MB | 8081 | `--embedding --pooling mean --ctx-size 2048 -b 2048 -ub 2048` |

Paths resolve under `~/.cache/huggingface/hub/models--<HF id>/snapshots/<rev>/`.

## Configuration

Copy `.env.example` to `.env`. Important knobs:

### LLM (query / generation)

| Variable              | Default                    | Description                       |
| --------------------- | -------------------------- | --------------------------------- |
| `LLM_BINDING`         | `openai`                   | OpenAI-compatible backend         |
| `LLM_BINDING_HOST`    | `http://127.0.0.1:8080/v1` | llama-server LLM endpoint         |
| `LLM_MODEL`           | `lfm2.5-1.2b-thinking`     | Must match llama-server `--alias` |
| `LLM_BINDING_API_KEY` | `sk-no-key-needed`         | Dummy key (see below)             |

### Extract LLM

| Variable                      | Default                    | Description                         |
| ----------------------------- | -------------------------- | ----------------------------------- |
| `EXTRACT_LLM_BINDING`         | `openai`                   | OpenAI-compatible backend           |
| `EXTRACT_LLM_BINDING_HOST`    | `http://127.0.0.1:8082/v1` | Dedicated extract llama-server      |
| `EXTRACT_LLM_MODEL`           | `lfm2-350m-extract`        | Must match extract server `--alias` |
| `EXTRACT_LLM_BINDING_API_KEY` | `sk-no-key-needed`         | Dummy key                           |

### Embeddings

| Variable                    | Default                    | Description                           |
| --------------------------- | -------------------------- | ------------------------------------- |
| `EMBEDDING_BINDING`         | `openai`                   | OpenAI-compatible backend             |
| `EMBEDDING_BINDING_HOST`    | `http://127.0.0.1:8081/v1` | llama-server embedding endpoint       |
| `EMBEDDING_MODEL`           | `bge-m3`                   | Must match llama-server `--alias`     |
| `EMBEDDING_BINDING_API_KEY` | `sk-no-key-needed`         | Dummy key                             |
| `EMBEDDING_DIM`             | `1024`                     | bge-m3 output dimension               |
| `EMBEDDING_TOKEN_LIMIT`     | `2048`                     | Must match embed `--ctx-size` / `-ub` |

### Reranker

Off by default (`RERANK_BINDING=null`). No local option in LightRAG.

### Storage

Default is local files under `./rag_storage`. For production, uncomment
PostgreSQL or Neo4j lines in `.env.example`.

### LightRAG server

| Variable           | Default     | Description                       |
| ------------------ | ----------- | --------------------------------- |
| `LIGHTRAG_API_KEY` | (empty)     | API key for the LightRAG server   |
| `HOST`             | `127.0.0.1` | local-only; use `0.0.0.0` for LAN |
| `PORT`             | `9621`      | Server port                       |

### Chunking and ingest

| Variable                       | Default | Description                                                  |
| ------------------------------ | ------- | ------------------------------------------------------------ |
| `CHUNK_SIZE`                   | `1200`  | Tokens per chunk                                             |
| `CHUNK_OVERLAP_SIZE`           | `100`   | Overlap between chunks                                       |
| `MAX_PARALLEL_INSERT`          | `1`     | Keep at 1 on 8GB                                             |
| `EXTRACT_MAX_ASYNC_LLM`        | `1`     | Concurrent extract LLM calls                                 |
| `MAX_ASYNC_LLM`                | `1`     | Concurrent base LLM calls                                    |
| `ENABLE_LLM_CACHE_FOR_EXTRACT` | `true`  | Cache extract results for reruns                             |
| `ENTITY_EXTRACTION_USE_JSON`   | `true`  | Required for LFM2-Extract (delimiter mode yields 0 entities) |
| `MAX_GLEANING`                 | `0`     | Second extract pass overflows 16k ctx; leave at 0            |

## Dummy API key

`llama-server` ignores `Authorization` unless started with `--key`. LightRAG's
OpenAI client only sends a key if `LLM_BINDING_API_KEY` /
`EMBEDDING_BINDING_API_KEY` is set. If unset it reads `OPENAI_API_KEY` and
raises `KeyError`. Use a non-empty placeholder (`sk-no-key-needed`).

## Entity extraction

During ingest, LightRAG chunks each document and calls the extract LLM per
chunk. With `ENTITY_EXTRACTION_USE_JSON=true`, the model returns JSON
(`entities` / `relationships`). That fills the NetworkX graph used by `local`,
`global`, `hybrid`, and `mix`. `naive` skips the graph and uses vectors only.

`LFM2.5-1.2B-Thinking` returns prose, so the graph stays empty. Use
`LFM2-350M-Extract` on `:8082` for structured extraction.

LFM2-Extract often emits `entity_name` / `entity_type` instead of LightRAG's
`name` / `type`. `scripts/rag_setup.py` remaps those fields and drops echoed
template placeholders like `<entity_name>`.

Check the graph after ingest:

```bash
# expect > 0; full corpus ≈ 700 / 400
python3 - <<'EOF'
import xml.etree.ElementTree as ET
t = ET.parse('rag_storage/graph_chunk_entity_relation.graphml')
ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}
print(len(t.getroot().findall('.//g:node', ns)), 'nodes,',
      len(t.getroot().findall('.//g:edge', ns)), 'edges')
EOF
```

## Troubleshooting (local llama.cpp)

| Symptom                                                    | Likely cause                                 | Fix                                                                       |
| ---------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------- |
| `input … too large … physical batch size (512)` on embed   | Default `-ub 512`                            | Restart embed; `start_servers.sh` sets `-b 2048 -ub 2048`                 |
| `input (17022 tokens) … batch size (2048)` on entity flush | Several long texts in one `/embeddings` call | `EMBEDDING_TOKEN_LIMIT=2048` + one-text-at-a-time embed in `rag_setup.py` |
| `exceed_context_size_error` on extract (~16k > ctx)        | JSON prompts + gleaning history              | Extract `--ctx-size 16384`; `MAX_GLEANING=0`                              |
| `Complete delimiter can not be found` / `0 Ent + 0 Rel`    | Delimiter mode vs JSON-native model          | `ENTITY_EXTRACTION_USE_JSON=true`                                         |
| Connection refused with `localhost`                        | IPv6 `::1` vs IPv4 bind                      | Use `127.0.0.1` in `.env`                                                 |
| OOM / servers die on 8GB                                   | All three models loaded                      | `start ingest` or `start query`, not `start all`                          |

## Scraper

```bash
# Full scrape (118 case studies)
uv run python scripts/scrape_case_studies.py

# Subset
uv run python scripts/scrape_case_studies.py --limit 5

# Concurrency
uv run python scripts/scrape_case_studies.py --concurrency 4

# Custom output dir
uv run python scripts/scrape_case_studies.py --output my_data
```

Output files:

- `data/case_studies.jsonl`: incremental, one object per line
- `data/case_studies.json`: final array in sitemap order
- `data/scrape-errors.log`: URLs that failed after retries

## Retrieval modes

| Mode     | What it does               | Best for                         |
| -------- | -------------------------- | -------------------------------- |
| `local`  | Entity lookup in the graph | Specific client / tech questions |
| `global` | Broad graph traversal      | Cross-case themes                |
| `hybrid` | local + global             | Detail plus breadth              |
| `naive`  | Vector similarity only     | Baseline                         |
| `mix`    | Graph + vector             | General queries                  |

## Project structure

```tree
ee-case-studies/
├── data/
│   ├── case_studies.json        # Scraped case studies (118)
│   └── case_studies.jsonl       # Incremental scrape backup
├── scripts/
│   ├── scrape_case_studies.py   # Concurrent scraper
│   ├── ingest.py                # LightRAG ingestion (resumable)
│   ├── query.py                 # Query CLI
│   ├── rag_setup.py             # Shared LightRAG init from .env
│   └── start_servers.sh         # Phased start/stop for llama.cpp
├── eval/
│   ├── cases.py                 # Eval cases
│   └── run_eval.py              # Eval runner
├── tests/
├── logs/                        # llama-server logs/pids (gitignored)
├── rag_storage/                 # Index (gitignored; keep it to resume)
├── .env.example
├── pyproject.toml
└── README.md
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Evaluation

`eval/` measures retrieval quality:

1. Add cases in `eval/cases.py` (query, expected entities, expected sources)
2. Run `uv run python eval/run_eval.py`
3. Compare precision / recall / F1 per mode

## License

AGPL-3.0. See [LICENSE](LICENSE).
