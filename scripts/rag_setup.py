"""Shared LightRAG construction from .env for ingest.py / query.py."""

from __future__ import annotations

import json
import os
import socket
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv
from lightrag import LightRAG
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.llm_roles import RoleLLMConfig
from lightrag.utils import EmbeddingFunc

ROOT = Path(__file__).resolve().parents[1]

# LFM2-Extract often emits entity_name/entity_type/...; LightRAG JSON mode
# expects name/type/description (and source/target/keywords for relations).
_ENTITY_FIELD_ALIASES = {
    "name": "name",
    "entity_name": "name",
    "type": "type",
    "entity_type": "type",
    "description": "description",
    "entity_description": "description",
}
_RELATION_FIELD_ALIASES = {
    "source": "source",
    "source_entity": "source",
    "target": "target",
    "target_entity": "target",
    "keywords": "keywords",
    "relationship_keywords": "keywords",
    "description": "description",
    "relationship_description": "description",
}


def load_env() -> None:
    """Load project .env (does not override already-set process env)."""
    load_dotenv(ROOT / ".env", override=False)


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"missing required env var: {name} (copy .env.example → .env)")
    return value


def _host_up(base_url: str, timeout: float = 0.5) -> bool:
    """True if the host:port from an OpenAI-style base URL accepts TCP."""
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _remap(obj: dict, aliases: dict[str, str]) -> dict:
    out: dict = {}
    for key, value in obj.items():
        dest = aliases.get(key)
        if dest and dest not in out:
            out[dest] = value
    return out


def _is_prompt_placeholder(value: object) -> bool:
    """True if the model echoed a LightRAG template token like <entity_name>."""
    if not isinstance(value, str):
        return False
    s = value.strip()
    return len(s) >= 3 and s.startswith("<") and s.endswith(">")


def _normalize_extract_json(text: str) -> str:
    """Map LFM2-Extract JSON shapes onto LightRAG's expected schema."""
    stripped = text.strip()
    if not stripped.startswith(("{", "[")):
        return text
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            import json_repair

            parsed = json_repair.loads(stripped)
        except Exception:
            return text

    if isinstance(parsed, list):
        parsed = {"entities": parsed, "relationships": []}
    if not isinstance(parsed, dict):
        return text

    # Single entity object (no entities wrapper)
    if "entities" not in parsed and any(
        k in parsed for k in ("entity_name", "name", "entity_type", "type")
    ):
        relationships = parsed.pop("relationships", [])
        if not isinstance(relationships, list):
            relationships = []
        parsed = {"entities": [parsed], "relationships": relationships}

    entities = parsed.get("entities", [])
    relationships = parsed.get("relationships", [])
    if not isinstance(entities, list) or not isinstance(relationships, list):
        return text

    clean_entities = []
    for e in entities:
        if not isinstance(e, dict):
            continue
        item = _remap(e, _ENTITY_FIELD_ALIASES)
        if _is_prompt_placeholder(item.get("name")) or _is_prompt_placeholder(
            item.get("type")
        ):
            continue
        clean_entities.append(item)

    clean_rels = []
    for rel in relationships:
        if not isinstance(rel, dict):
            continue
        item = _remap(rel, _RELATION_FIELD_ALIASES)
        if _is_prompt_placeholder(item.get("source")) or _is_prompt_placeholder(
            item.get("target")
        ):
            continue
        if isinstance(item.get("keywords"), list):
            item["keywords"] = ", ".join(str(k) for k in item["keywords"])
        clean_rels.append(item)

    parsed["entities"] = clean_entities
    parsed["relationships"] = clean_rels
    return json.dumps(parsed, ensure_ascii=False)


def _openai_llm(model: str, base_url: str, api_key: str, *, normalize_extract: bool = False):
    async def _complete(
        prompt,
        system_prompt=None,
        history_messages=None,
        **kwargs,
    ):
        if history_messages is None:
            history_messages = []
        # llama-server does not implement OpenAI json_object response_format.
        kwargs.pop("response_format", None)
        result = await openai_complete_if_cache(
            model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            base_url=base_url,
            api_key=api_key,
            **kwargs,
        )
        if normalize_extract and isinstance(result, str):
            return _normalize_extract_json(result)
        return result

    return _complete


def build_rag(working_dir: str | Path | None = None) -> LightRAG:
    """Build a LightRAG instance wired to the local llama-server trio.

    On 8GB machines, ingest runs extract+embed only. If the query LLM host
    (:8080) is down but extract (:8082) is up, the base LLM falls back to the
    extract server so ingest can proceed.
    """
    load_env()

    llm_model = _require("LLM_MODEL")
    llm_host = _require("LLM_BINDING_HOST")
    llm_key = _require("LLM_BINDING_API_KEY")

    embed_model = _require("EMBEDDING_MODEL")
    embed_host = _require("EMBEDDING_BINDING_HOST")
    embed_key = _require("EMBEDDING_BINDING_API_KEY")
    embed_dim = int(os.getenv("EMBEDDING_DIM", "1024"))

    extract_model = os.getenv("EXTRACT_LLM_MODEL")
    extract_host = os.getenv("EXTRACT_LLM_BINDING_HOST")
    extract_key = os.getenv("EXTRACT_LLM_BINDING_API_KEY", llm_key)

    if not _host_up(llm_host) and extract_host and _host_up(extract_host):
        print(
            f"note: query LLM {llm_host} is down; "
            f"using extract server {extract_host} as base LLM for this run"
        )
        llm_host = extract_host
        llm_model = extract_model or llm_model
        llm_key = extract_key

    if not _host_up(embed_host):
        raise SystemExit(
            f"embedding server not reachable at {embed_host} — "
            f"run: scripts/start_servers.sh start ingest"
        )

    chunk_size = int(os.getenv("CHUNK_SIZE", "1200"))
    chunk_overlap = int(os.getenv("CHUNK_OVERLAP_SIZE", "100"))
    max_async = int(os.getenv("MAX_ASYNC_LLM", "1"))
    # LFM2-Extract is JSON-native; delimiter mode yields 0 Ent + delimiter warnings.
    use_json_extract = os.getenv("ENTITY_EXTRACTION_USE_JSON", "true").lower() == "true"
    # Gleaning resends the first extract + history and overflows 16k ctx on
    # 8GB machines (seen 16644 > 16384). One pass is enough for this corpus.
    max_gleaning = int(os.getenv("MAX_GLEANING", "0"))
    # Must be <= llama-server -ub/--ubatch-size (and --ctx-size) for bge-m3.
    # Hot entities like "Equal Experts" accumulate huge merged summaries; LightRAG
    # truncates VDB payloads to this limit before embedding.
    embed_max_tokens = int(os.getenv("EMBEDDING_TOKEN_LIMIT", "2048"))

    async def _embed(texts: list[str], max_token_size: int | None = None, **_kwargs):
        # llama-server packs every input in one request into the physical batch.
        # Sending N long texts at once sums tokens (seen 17022 > ubatch 2048).
        import numpy as np

        limit = max_token_size if max_token_size is not None else embed_max_tokens
        vectors = []
        for text in texts:
            batch = await openai_embed.func(
                [text],
                model=embed_model,
                base_url=embed_host,
                api_key=embed_key,
                embedding_dim=embed_dim,
                max_token_size=limit,
            )
            vectors.append(batch[0])
        return np.stack(vectors)

    embedding_func = EmbeddingFunc(
        embedding_dim=embed_dim,
        max_token_size=embed_max_tokens,
        model_name=embed_model,
        func=_embed,
    )

    role_llm_configs = None
    if extract_model and extract_host:
        role_llm_configs = {
            "extract": RoleLLMConfig(
                func=_openai_llm(
                    extract_model,
                    extract_host,
                    extract_key,
                    normalize_extract=use_json_extract,
                ),
                max_async=int(os.getenv("EXTRACT_MAX_ASYNC_LLM", "1")),
                metadata={
                    "binding": "openai",
                    "model": extract_model,
                    "host": extract_host,
                },
            )
        }

    storage = Path(working_dir) if working_dir else ROOT / "rag_storage"
    return LightRAG(
        working_dir=str(storage),
        llm_model_func=_openai_llm(llm_model, llm_host, llm_key),
        llm_model_name=llm_model,
        llm_model_max_async=max_async,
        embedding_func=embedding_func,
        chunk_token_size=chunk_size,
        chunk_overlap_token_size=chunk_overlap,
        entity_extraction_use_json=use_json_extract,
        entity_extract_max_gleaning=max_gleaning,
        role_llm_configs=role_llm_configs,
    )
