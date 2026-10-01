"""Knowledge-graph construction over chunks, extracted entities and TF-IDF
keywords, plus community detection (Louvain). This is the local, dependency-light
graph backbone for the GraphRAG layer (community summaries live in graphrag.py)."""

from __future__ import annotations

import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np

from .models import Chunk, Entity, GraphData, GraphEdge, GraphNode
from .text_utils import idf, text_terms, term_freqs, top_keywords

# node id helpers -------------------------------------------------------------
CHUNK_PREFIX = "chunk:"
KEYWORD_PREFIX = "kw:"
ENTITY_PREFIX = "ent:"


def chunk_id_of(node_id: str) -> str:
    return node_id.split(":", 1)[1] if ":" in node_id else node_id


def build_graph(
    chunks: list[Chunk],
    chunk_vectors: np.ndarray | None = None,
    entities: list[Entity] | None = None,
    relations: list[dict] | None = None,
    keywords_per_chunk: int = 6,
    similarity_threshold: float = 0.55,
    top_sim_neighbors: int = 3,
) -> tuple[GraphData, dict[str, float]]:
    """Build a heterogeneous graph:
    chunk --kw--> keyword  (tf-idf weight)
    chunk --sim--> chunk   (cosine similarity, top neighbors)
    chunk --mention--> entity
    entity --rel--> entity (from LLM extraction, labelled predicate)
    keyword --cooccur--> keyword (pairs appearing in same chunks)

    Returns (GraphData, idf_map)."""
    entities = entities or []
    relations = relations or []
    idf_map: dict[str, float] = {}
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    edge_weight: dict[tuple[str, str], float] = defaultdict(float)
    edge_kind: dict[tuple[str, str], str] = {}
    edge_label: dict[tuple[str, str], str] = {}

    # ---- keyword layer (TF-IDF) --------------------------------------------
    corpus_term_sets = [set(text_terms(c.text)) for c in chunks]
    idf_map = idf(corpus_term_sets)
    chunk_keywords: dict[str, list[str]] = {}
    kw_docs: dict[str, list[str]] = defaultdict(list)  # keyword -> chunk ids

    for c in chunks:
        tf = term_freqs(text_terms(c.text))
        kws = top_keywords(tf, idf_map, k=keywords_per_chunk)
        chunk_keywords[c.id] = kws
        cid = f"{CHUNK_PREFIX}{c.id}"
        nodes.setdefault(cid, GraphNode(id=cid, label=c.title or c.id, kind="chunk",
                                        meta={"chunk_id": c.id, "source": c.source,
                                              "keywords": kws, "title": c.title}))
        for kw in kws:
            kid = f"{KEYWORD_PREFIX}{kw}"
            nodes.setdefault(kid, GraphNode(id=kid, label=kw, kind="keyword", meta={}))
            kw_docs[kw].append(c.id)
            key = tuple(sorted([cid, kid]))
            edge_weight[key] += c.n_tokens or 1
            edge_kind[key] = "kw"

    # keyword co-occurrence edges
    for c in chunks:
        kws = chunk_keywords[c.id]
        for a, b in itertools.combinations(kws, 2):
            ka, kb = sorted([a, b])
            key = (f"{KEYWORD_PREFIX}{ka}", f"{KEYWORD_PREFIX}{kb}")
            edge_weight[key] += 1.0
            edge_kind.setdefault(key, "cooccur")

    # ---- chunk similarity edges -------------------------------------------
    if chunk_vectors is not None and len(chunk_vectors) == len(chunks):
        norms = np.linalg.norm(chunk_vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normed = chunk_vectors / norms
        sim = normed @ normed.T
        for i in range(len(chunks)):
            order = np.argsort(sim[i])[::-1][: top_sim_neighbors + 1]
            for j in order:
                if j == i:
                    continue
                s = float(sim[i, j])
                if s < similarity_threshold:
                    continue
                key = tuple(sorted([f"{CHUNK_PREFIX}{chunks[i].id}", f"{CHUNK_PREFIX}{chunks[j].id}"]))
                edge_weight[key] = max(edge_weight[key], s)
                edge_kind[key] = "sim"

    # ---- entities ----------------------------------------------------------
    ent_by_name: dict[str, Entity] = {}
    for e in entities:
        key = e.name.strip().lower()
        if not key:
            continue
        if key in ent_by_name:
            ent_by_name[key].mentions += e.mentions
            if e.note and not ent_by_name[key].note:
                ent_by_name[key].note = e.note
        else:
            ent_by_name[key] = e
    chunk_text_lower = {c.id: c.text.lower() for c in chunks}
    for e in ent_by_name.values():
        eid = f"{ENTITY_PREFIX}{e.name.strip().lower().replace(' ', '_')[:60]}"
        if eid not in nodes:
            nodes[eid] = GraphNode(id=eid, label=e.name, kind="entity",
                                   meta={"type": e.type, "note": e.note})
        # mention edges: entity appears inside a chunk's text
        name_l = e.name.strip().lower()
        for c in chunks:
            if name_l and name_l in chunk_text_lower[c.id]:
                key = (f"{CHUNK_PREFIX}{c.id}", eid)
                edge_weight[key] += 1.0
                edge_kind[key] = "mention"

    for r in relations:
        src = str(r.get("source", "")).strip().lower()
        tgt = str(r.get("target", "")).strip().lower()
        rel = str(r.get("relation", "related_to")).strip().lower().replace(" ", "_")
        if not src or not tgt or src == tgt:
            continue
        sid = f"{ENTITY_PREFIX}{src[:60].replace(' ', '_')}"
        tid = f"{ENTITY_PREFIX}{tgt[:60].replace(' ', '_')}"
        for nid, label, ntype in [(sid, r.get("source"), "concept"), (tid, r.get("target"), "concept")]:
            if nid not in nodes:
                nodes[nid] = GraphNode(id=nid, label=label, kind="entity", meta={"type": ntype, "note": ""})
        key = tuple(sorted([sid, tid]))
        edge_weight[key] += 2.0
        edge_kind[key] = "rel"
        edge_label[key] = rel

    # materialize edges
    for (a, b), w in edge_weight.items():
        edges.append(GraphEdge(src=a, tgt=b, weight=round(w, 4),
                               kind=edge_kind.get((a, b), "co"),
                               label=edge_label.get((a, b), "")))

    graph = GraphData(nodes=list(nodes.values()), edges=edges)
    return graph, idf_map


def detect_communities(graph: GraphData, seed: int = 42) -> GraphData:
    """Louvain community detection over the union graph; fills
    graph.communities and graph.chunk_community."""
    G = nx.Graph()
    for n in graph.nodes:
        G.add_node(n.id)
    for e in graph.edges:
        if G.has_edge(e.src, e.tgt):
            G[e.src][e.tgt]["weight"] += e.weight
        else:
            G.add_edge(e.src, e.tgt, weight=e.weight)
    if G.number_of_nodes() == 0:
        graph.communities = {}
        graph.chunk_community = {}
        return graph

    try:
        comms = nx.community.louvain_communities(G, weight="weight", seed=seed)
    except Exception:
        comms = [set(G.nodes())]  # fallback: one big community
    graph.communities = {f"com{i}": sorted(m) for i, m in enumerate(comms)}
    graph.chunk_community = {}
    for cid, members in graph.communities.items():
        for node_id in members:
            if node_id.startswith(CHUNK_PREFIX):
                graph.chunk_community[node_id.split(":", 1)[1]] = cid
    return graph


def community_labels(graph: GraphData, top_k: int = 8) -> dict[str, list[str]]:
    """Representative labels per community (entities first, then keywords)."""
    out: dict[str, list[str]] = {}
    node_by_id = {n.id: n for n in graph.nodes}
    for cid, members in graph.communities.items():
        ents = [node_by_id[m].label for m in members if m in node_by_id and node_by_id[m].kind == "entity"]
        kws = [node_by_id[m].label for m in members if m in node_by_id and node_by_id[m].kind == "keyword"]
        out[cid] = (ents[:top_k] + kws[:top_k])[:top_k]
    return out


def save_graph(graph: GraphData, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph.model_dump_json(indent=2), encoding="utf-8")


def load_graph(path: str | Path) -> GraphData:
    p = Path(path)
    if not p.exists():
        return GraphData()
    return GraphData.model_validate_json(p.read_text(encoding="utf-8"))


def keyword_idf_from_chunks(chunks: list[Chunk]) -> dict[str, float]:
    return idf([set(text_terms(c.text)) for c in chunks])