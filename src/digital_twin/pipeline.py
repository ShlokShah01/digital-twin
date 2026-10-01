"""End-to-end build pipeline: raw files -> documents -> chunks -> embeddings ->
vector store -> knowledge graph + communities + summaries -> style -> profile."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .embedder import Embedder
from .extraction import (
    decision_patterns_from,
    entities_from,
    facts_from,
    merge_entities,
    merge_patterns,
    merge_preferences,
    preferences_from,
)
from .graph import build_graph
from .graphrag import GraphRAG
from .ingest import chunk_documents, load_directory, load_file
from .llm import ChatClient, LLMUnavailable
from .models import Chunk, Document
from .profile import assemble_profile, save_profile
from .style import analyze_style
from .vector_store import VectorStore

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BuildResult:
    def __init__(self, cfg: Config, n_docs=0, n_chunks=0, n_facts=0, graph=None,
                 style_ok=False, llm_used=False):
        self.cfg = cfg
        self.n_documents = n_docs
        self.n_chunks = n_chunks
        self.n_facts = n_facts
        self.n_entities = 0
        self.n_communities = 0
        self.n_edges = 0
        self.n_nodes = 0
        self.style_ok = style_ok
        self.llm_used = llm_used


def build(cfg: Config, raw_dir: str | Path | None = None,
          use_llm: bool | None = None) -> BuildResult:
    raw_dir = Path(raw_dir) if raw_dir else cfg.raw_dir
    docs = load_directory(raw_dir)
    if not docs:
        raise RuntimeError(f"No supported files (txt/md/json/csv) found in {raw_dir}")

    llm = ChatClient(cfg)
    allow_llm = use_llm is not False
    llm_enabled = llm.enabled and allow_llm

    chunks = chunk_documents(docs, cfg.chunk_words, cfg.chunk_overlap)
    all_text = "\n\n".join(d.text for d in docs)

    # ---- embeddings + vector store ----------------------------------------
    embedder = Embedder(cfg.embed_model)
    vectors = embedder.embed([c.text for c in chunks])
    dim = vectors.shape[1] if vectors.shape[0] else embedder.dim()
    vec_store = VectorStore(cfg.lancedb_path, dim=dim)
    vec_store.drop()
    rows = []
    epoch_hashes: set[str] = set()
    for c, v in zip(chunks, vectors):
        th = hashlib.sha1(c.text.encode("utf-8", "ignore")).hexdigest()
        if th in epoch_hashes:
            continue
        epoch_hashes.add(th)
        rows.append({
            "chunk_id": c.id,
            "text": c.text,
            "source": c.source,
            "title": c.title,
            "doc_id": c.doc_id,
            "n_tokens": c.n_tokens,
            "text_hash": th,
            "vector": v.tolist(),
        })
    vec_store.add(rows)
    # keep only the chunks we actually stored
    stored_ids = {r["chunk_id"] for r in rows}
    chunks = [c for c in chunks if c.id in stored_ids]

    # ---- style --------------------------------------------------------------
    style = analyze_style(all_text, n_chunks=len(chunks))

    # ---- extraction (LLM per-document, heuristic offline fallback) -----------
    name_guess = ""
    preferences = []
    patterns = []
    facts = []
    entities = []
    relations: list[dict] = []
    llm_used = False
    for doc in docs:
        out: dict = {}
        if llm_enabled:
            try:
                out = llm.extract(doc.text, doc.title) or {}
            except LLMUnavailable:
                llm_enabled = False
                llm_used = False
            except Exception as e:  # noqa: BLE001
                log.warning("extraction failed on %s: %s", doc.title, e)
                out = {}
        if not out:
            from .extraction import offline_extract
            llm_used = bool(llm_used)
            out = offline_extract(doc.text)
        else:
            llm_used = True
        if not out:
            continue
        if not name_guess:
            name_guess = str(out.get("name_guess") or "").strip()
        entities = merge_entities(entities, entities_from(out))
        preferences = merge_preferences(preferences, preferences_from(out))
        patterns = merge_patterns(patterns, decision_patterns_from(out))
        relations.extend(out.get("relations") or [])
        for f in facts_from(out):
            facts.append(f)

    # ---- knowledge graph + GraphRAG -----------------------------------------
    graph, idf_map = build_graph(chunks, vectors, entities, relations)
    graphrag = GraphRAG.build(chunks, graph, embedder, llm, cfg.max_community_summaries)

    # ---- profile --------------------------------------------------------------
    result = BuildResult(cfg, n_docs=len(docs), n_chunks=len(chunks),
                         n_facts=len(facts), graph=graph, style_ok=True, llm_used=llm_used)
    profile = assemble_profile(
        name_guess=name_guess, style=style, preferences=preferences,
        decision_patterns=patterns, facts=facts, entities=entities,
        chunks=chunks, llm=llm, built_at=_now(),
    )
    result.n_entities = len(entities)
    result.n_communities = len(graphrag.graph.communities)
    result.n_nodes = len(graphrag.graph.nodes)
    result.n_edges = len(graphrag.graph.edges)

    # ---- persist --------------------------------------------------------------
    cfg.twin_dir.mkdir(parents=True, exist_ok=True)
    save_profile(profile, cfg.profile_path)
    graphrag.save(cfg.graph_path, cfg.community_path)
    (cfg.index_path).write_text(json.dumps([c.model_dump() for c in chunks], indent=1),
                                encoding="utf-8")
    return result


def add_source(cfg: Config, path: str | Path) -> dict:
    """Incrementally ingest one more file: chunk, embed, append to the vectors."""
    path = Path(path)
    docs = load_file(path)
    if not docs:
        raise RuntimeError(f"Unsupported or missing file: {path}")
    embedder = Embedder(cfg.embed_model)
    vec_store = VectorStore(cfg.lancedb_path, dim=embedder.dim())
    existing_hashes = {r.get("text_hash") for r in vec_store.all_rows()} if vec_store.exists() else set()
    chunk_overlap = cfg.chunk_overlap
    new_chunks = chunk_documents(docs, cfg.chunk_words, chunk_overlap)
    added = 0
    for c in new_chunks:
        th = hashlib.sha1(c.text.encode("utf-8", "ignore")).hexdigest()
        if th in existing_hashes:
            continue
        vec = embedder.embed_one(c.text)
        vec_store.add([{
            "chunk_id": c.id + "-inc",
            "text": c.text,
            "source": c.source,
            "title": c.title,
            "doc_id": c.doc_id,
            "n_tokens": c.n_tokens,
            "text_hash": th,
            "vector": vec.tolist(),
        }])
        existing_hashes.add(th)
        added += 1
    return {"chunks_added": added, "source": str(path)}