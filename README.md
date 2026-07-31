# EE Case Studies — LightRAG

Graph-based RAG pipeline over Equal Experts case studies, built with [LightRAG](https://github.com/HKUDS/LightRAG) and local LLMs via Ollama.

## What This Does

- Scrapes all case studies from [equalexperts.com/case-studies](https://www.equalexperts.com/case-studies/) (118 total)
- Indexes them into a LightRAG knowledge graph (entities + relationships + vector embeddings)
- Provides a query interface with 5 retrieval modes: local, global, hybrid, naive, mix
- Runs entirely local — no API keys, no cloud services

## Tech Stack

| Component | Choice |
|-----------|--------|
| RAG framework | LightRAG (`lightrag-hku`) |
| LLM | Ollama `llama3.2` |
| Embeddings | Ollama `nomic-embed-text` (768-dim) |
| Scraper | `requests` + `BeautifulSoup` |
| Python | 3.12+ |
| Package manager | uv |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/TMFNK/ee-case-studies.git
cd ee-case-studies

# 2. Install dependencies
uv sync

# 3. Start Ollama models
ollama pull llama3.2
ollama pull nomic-embed-text

# 4. Configure environment
cp .env.example .env

# 5. Scrape case studies
uv run python scripts/scrape_case_studies.py

# 6. Ingest into LightRAG
uv run python scripts/ingest.py

# 7. Query
uv run python scripts/query.py
# Or use the web UI at http://localhost:9621
```

## Project Structure

```
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
├── .env.example                 # LightRAG config template
├── pyproject.toml
└── README.md
```

## License

AGPL-3.0