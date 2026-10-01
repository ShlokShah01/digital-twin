"""Lightweight GraphRAG over the local knowledge graph.

Two query paths (mirroring Microsoft GraphRAG's local/global search at a scale
that runs offline):
  * local_search  - seed entities from the query, expand 1 hop, pull facts
  * global_search - score pre-built community summaries against the query

Community summaries are generated once at build time by the LLM (with a
keyword-based fallback when no API key is present)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .models import Chunk, GraphData
from .graph import CHUNK_PREFIX, ENTITY_PREFIX, KEYWORD_PREFIX, community_labels, detect_communities
from .vector_store import cosine


class GraphRAG:
    def __init__(self, embedder, graph: GraphData | None = None,
                 chunks: dict[str, Chunk] | None = None,
                 community_summaries: list[dict] | None = None):
        self.embedder = embedder
        self.graph = graph or GraphData()
        self.chunks = chunks or {}
        self.community_summaries = community_summaries or []
        self._summary_vecs: list[np.ndarray] = []
        self._index()

    # -------------------------------------------------------------------------
    # indexing
    # -------------------------------------------------------------------------
    def _index(self) -> None:
        self._node_by_id = {n.id: n for n in self.graph.nodes}
        self._adjacency: dict[str, list[tuple[str, float, str, str]]] = defaultdict(list)
        for e in self.graph.edges:
            self._adjacency[e.src].append((e.tgt, e.weight, e.kind, e.label))
            self._adjacency[e.tgt].append((e.src, e.weight, e.kind, e.label))
        self._comm_members = self.graph.communities
        if self.community_summaries:
            vecs = self.embedder.embed([c["summary"] for c in self.community_summaries])
            self._summary_vecs = [vecs[i] for i in range(len(self.community_summaries))]

    # -------------------------------------------------------------------------
    # build-time community summaries
    # -------------------------------------------------------------------------
    @classmethod
    def build(cls, chunks_list: list[Chunk], graph: GraphData, embedder, llm=None,
              max_communities: int = 12) -> "GraphRAG":
        graph = detect_communities(graph)
        chunks_map = {c.id: c for c in chunks_list}
        labels = community_labels(graph)
        node_by_id = {n.id: n for n in graph.nodes}

        # sort communities by size, keep the biggest ones summarized
        ordered = sorted(graph.communities.items(), key=lambda kv: len(kv[1]), reverse=True)
        ordered = ordered[:max_communities]

        summaries: list[dict] = []
        for cid, members in ordered:
            member_entities = [node_by_id[m].label for m in members
                               if m in node_by_id and node_by_id[m].kind == "entity"]
            member_kws = [node_by_id[m].label for m in members
                          if m in node_by_id and node_by_id[m].kind == "keyword"]
            member_texts = []
            for m in members:
                if m.startswith(CHUNK_PREFIX):
                    cid_chunk = m.split(":", 1)[1]
                    if cid_chunk in chunks_map:
                        member_texts.append(chunks_map[cid_chunk].text)
            if not member_texts and not member_entities:
                continue
            summary = _summarize_community(member_entities, member_kws, member_texts, llm)
            summaries.append({
                "id": cid,
                "summary": summary,
                "keywords": (member_kws + member_entities)[:12],
                "entities": member_entities[:12],
                "size": len(members),
            })

        g = cls(embedder, graph=graph, chunks=chunks_map, community_summaries=summaries)
        return g

    # -------------------------------------------------------------------------
    # query: local search
    # -------------------------------------------------------------------------
    def local_search(self, query: str, query_terms: list[str], query_vec: np.ndarray,
                     k: int = 12) -> str:
        if not self.graph.nodes:
            return ""
        q = set(query.lower().split())
        qt = set(query_terms) | q
        scored_nodes = []
        for n in self.graph.nodes:
            label_l = n.label.lower()
            note_l = str(n.meta.get("note", "")).lower()
            score = 0.0
            for t in qt:
                if t and t in label_l:
                    score += 2.0
                if t and t in note_l:
                    score += 1.0
            if n.kind == "entity":
                score += 0.4  # slight prior: entities are the graph's spine
            if score > 0:
                scored_nodes.append((score, n.id))
        scored_nodes.sort(reverse=True)
        seeds = [nid for _, nid in scored_nodes[: max(k // 2, 3)]]

        # expand one hop
        keep: set[str] = set(seeds)
        for s in seeds:
            for tgt, w, kind, label in sorted(self._adjacency.get(s, []), key=lambda x: -x[1])[:6]:
                keep.add(tgt)

        lines: list[str] = []
        facts: list[str] = []
        seen: set[str] = set()
        for nid in sorted(keep):
            if nid.startswith(CHUNK_PREFIX):
                cid = nid.split(":", 1)[1]
                if cid in self.chunks and cid not in seen:
                    seen.add(cid)
                    txt = self.chunks[cid].text
                    facts.append(f"- {txt[:400]} ({self.chunks[cid].title})")
            elif nid.startswith(ENTITY_PREFIX):
                n = self._node_by_id.get(nid)
                if n and n.label.lower() not in seen:
                    seen.add(n.label.lower())
                    note = n.meta.get("note", "")
                    rels = [f"{self._node_by_id.get(t, _dummy(t)).label}"
                            for t, w, kind, label in self._adjacency.get(nid, [])
                            if kind == "rel"][:5]
                    line = f"- {n.label}: {note}" if note else f"- {n.label}"
                    if rels:
                        line += f" (connected: {', '.join(rels)})"
                    facts.append(line)
            elif nid.startswith(KEYWORD_PREFIX):
                n = self._node_by_id.get(nid)
                if n:
                    lines.append(n.label)
        if not facts:
            return ""
        head = "Relevant graph context (entities, relationships and source fragments):\n"
        return head + "\n".join(facts[:14])

    # -------------------------------------------------------------------------
    # query: global search
    # -------------------------------------------------------------------------
    def global_search(self, query_vec: np.ndarray, query_terms: list[str],
                      k: int = 3) -> str:
        if not self.community_summaries:
            return ""
        qt = set(query_terms)
        scored = []
        for summ, vec in zip(self.community_summaries, self._summary_vecs):
            cos = cosine(query_vec, vec)
            kw_hit = sum(1 for kw in summ.get("keywords", []) if kw.lower() in qt)
            score = cos + 0.1 * kw_hit
            scored.append((score, summ))
        scored.sort(key=lambda x: x[0], reverse=True)
        picked = [s for sc, s in scored[:k] if sc > 0.05]
        if not picked:
            return ""
        out = ["Global themes from the person's knowledge graph (community summaries):"]
        for i, s in enumerate(picked, 1):
            out.append(f"{i}. {s['summary']}")
        return "\n".join(out)

    def stats(self) -> dict:
        return {
            "nodes": len(self.graph.nodes),
            "edges": len(self.graph.edges),
            "communities": len(self.graph.communities),
            "summaries": len(self.community_summaries),
        }

    # -------------------------------------------------------------------------
    # persistence
    # -------------------------------------------------------------------------
    def save(self, graph_path: str | Path, community_path: str | Path) -> None:
        from .graph import save_graph
        save_graph(self.graph, graph_path)
        Path(community_path).parent.mkdir(parents=True, exist_ok=True)
        Path(community_path).write_text(
            json.dumps(self.community_summaries, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, embedder, graph_path: str | Path, community_path: str | Path,
             chunks: dict[str, Chunk] | None = None) -> "GraphRAG":
        from .graph import load_graph
        graph = load_graph(graph_path)
        summ = []
        p = Path(community_path)
        if p.exists():
            try:
                summ = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                summ = []
        return cls(embedder, graph=graph, chunks=chunks, community_summaries=summ)


# ---------------------------------------------------------------------------
class _dummy:
    def __init__(self, label: str):
        self.label = label


def _summarize_community(entities, keywords, texts, llm) -> str:
    """LLM-written community summary, or a keyword fallback when no LLM."""
    if not texts and not entities and not keywords:
        return ""
    if llm is not None and hasattr(llm, "available") and llm.available and texts:
        joined = "\n".join(t[:400] for t in texts[:8])
        prompt = (
            "You are summarizing one community of facts about a single person, "
            "extracted from their journal, notes and messages.\n\n"
            f"Facts:\n{joined}\n\n"
            f"Entities: {', '.join(entities[:12]) or 'n/a'}\n"
            f"Keywords: {', '.join(keywords[:12]) or 'n/a'}\n\n"
            "Write ONE paragraph of 45-70 words capturing this person's stated "
            "preferences, decisions or habits in this area. Be concrete and "
            "neutral. Do not add facts that are not in the text."
        )
        try:
            s = llm.complete_text(prompt, temperature=0.2)
            if s and len(s.split()) >= 10:
                return s.strip()
        except Exception:
            pass
    head = ", ".join((entities + keywords)[:10]) or "untitled cluster"
    return f"Cluster around: {head}. Drawn from {len(texts)} fragments of the person's writing."