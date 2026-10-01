"""Central configuration. Everything is driven by environment variables or a
.env file next to the project root. No secrets are hardcoded anywhere."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

_TRUE = {"1", "true", "yes", "on", "y"}


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


@dataclass
class Config:
    # --- paths -------------------------------------------------------------
    root: Path = ROOT
    raw_dir: Path = Path(_env("DIGITAL_TWIN_RAW_DIR", str(ROOT / "data" / "raw")))
    twin_dir: Path = Path(_env("DIGITAL_TWIN_DIR", str(ROOT / "data" / "twin")))
    lancedb_path: Path = twin_dir / "lancedb"
    graph_path: Path = twin_dir / "graph.json"
    profile_path: Path = twin_dir / "profile.json"
    index_path: Path = twin_dir / "chunk_index.json"
    community_path: Path = twin_dir / "communities.json"

    # --- LLM (OpenAI-compatible) -------------------------------------------
    # Two optional keys in the same OpenAI-compatible format (e.g. NVIDIA NIM
    # `nvapi-...`). Both are used: requests are round-robined across the keys,
    # each key is rate-limited to `llm_rpm` requests/minute, and a failed
    # request is retried once against the other key.
    llm_api_key: str | None = _env("OPENAI_API_KEY")
    llm_api_key_2: str | None = _env("OPENAI_API_KEY_2")
    llm_base_url: str = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")
    llm_model: str = _env("DIGITAL_TWIN_LLM_MODEL", "gpt-4o-mini")
    llm_fallback_model: str = _env("DIGITAL_TWIN_LLM_FALLBACK_MODEL", "")
    llm_context_tokens: int = int(_env("DIGITAL_TWIN_LLM_CONTEXT", "131072"))
    llm_timeout: float = float(_env("DIGITAL_TWIN_LLM_TIMEOUT", "240"))
    llm_attempt_timeout: float = float(_env("DIGITAL_TWIN_LLM_ATTEMPT_TIMEOUT", "20"))
    llm_thinking: bool = _env("DIGITAL_TWIN_LLM_THINKING", "").lower() in _TRUE
    llm_rpm: float = float(_env("DIGITAL_TWIN_LLM_RPM", "40"))
    llm_enabled: bool = bool(llm_api_key or llm_api_key_2) and not _env(
        "DIGITAL_TWIN_NO_LLM", "").lower() in _TRUE

    @property
    def llm_keys(self) -> list[str]:
        """Configured API keys in priority order, empties dropped."""
        return [k for k in (self.llm_api_key, self.llm_api_key_2) if k]

    # --- models ------------------------------------------------------------
    embed_model: str = _env("DIGITAL_TWIN_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    laya_checkpoint: str = _env("DIGITAL_TWIN_LAYA_CHECKPOINT", "typed-decisions")
    laya_device: str = _env("DIGITAL_TWIN_LAYA_DEVICE", "cpu")
    laya_enabled: bool = not _env("DIGITAL_TWIN_NO_LAYA", "").lower() in _TRUE

    # --- RAG knobs ----------------------------------------------------------
    chunk_words: int = int(_env("DIGITAL_TWIN_CHUNK_WORDS", "150"))
    chunk_overlap: int = int(_env("DIGITAL_TWIN_CHUNK_OVERLAP", "30"))
    vector_k: int = int(_env("DIGITAL_TWIN_VECTOR_K", "256"))
    retrieve_k: int = int(_env("DIGITAL_TWIN_RETRIEVE_K", "24"))
    rerank_k: int = int(_env("DIGITAL_TWIN_RERANK_K", "6"))
    graph_k: int = int(_env("DIGITAL_TWIN_GRAPH_K", "12"))
    community_k: int = int(_env("DIGITAL_TWIN_COMMUNITY_K", "3"))
    max_community_summaries: int = int(_env("DIGITAL_TWIN_MAX_COMMUNITIES", "12"))

    # --- runtime flags ------------------------------------------------------
    verbose: bool = field(default=False)


def load_config() -> Config:
    return Config()