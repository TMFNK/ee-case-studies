"""Shared LightRAG construction from .env for ingest.py / query.py."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from lightrag import LightRAG
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.llm_roles import RoleLLMConfig
from lightrag.utils import EmbeddingFunc

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    """Load project .env (does not override already-set process env)."""
    load_dotenv(ROOT / ".env", override=False)


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"missing required env var: {name} (copy .env.example → .env)")
    return value


def _openai_llm(model: str, base_url: str, api_key: str):
    async def _complete(
        prompt,
        system_prompt=None,
        history_messages=None,
        **kwargs,
    ):
        if history_messages is None:
            history_messages = []
        return await openai_complete_if_cache(
            model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            base_url=base_url,
            api_key=api_key,
            **kwargs,
        )

    return _complete


def build_rag(working_dir: str | Path | None = None) -> LightRAG:
    """Build a LightRAG instance wired to the local llama-server trio."""
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

    chunk_size = int(os.getenv("CHUNK_SIZE", "1200"))
    chunk_overlap = int(os.getenv("CHUNK_OVERLAP_SIZE", "100"))

    async def _embed(texts: list[str]):
        return await openai_embed.func(
            texts,
            model=embed_model,
            base_url=embed_host,
            api_key=embed_key,
            embedding_dim=embed_dim,
        )

    embedding_func = EmbeddingFunc(
        embedding_dim=embed_dim,
        max_token_size=8192,
        model_name=embed_model,
        func=_embed,
    )

    role_llm_configs = None
    if extract_model and extract_host:
        role_llm_configs = {
            "extract": RoleLLMConfig(
                func=_openai_llm(extract_model, extract_host, extract_key),
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
        embedding_func=embedding_func,
        chunk_token_size=chunk_size,
        chunk_overlap_token_size=chunk_overlap,
        role_llm_configs=role_llm_configs,
    )
