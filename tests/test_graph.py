from digital_twin.graph import (
    build_graph, detect_communities, load_graph, save_graph,
)
from digital_twin.models import Chunk, Entity


def _chunks():
    texts = [
        "Alex prefers refurbished laptops and rides a bike to work in Portland.",
        "The two-week wait rule applies to anything over two hundred dollars.",
        "Sam and Alex play board games every week at the shop downtown.",
    ]
    return [Chunk(id=f"c{i}", doc_id="d0", source="demo.md",
                  title="demo", text=t, n_tokens=len(t.split()))
            for i, t in enumerate(texts)]


def test_build_graph_has_keyword_and_chunk_nodes():
    chunks = _chunks()
    graph, idf_map = build_graph(chunks)
    assert graph.nodes
    assert graph.edges
    assert any(n.id.startswith("chunk:") for n in graph.nodes)
    assert any(n.id.startswith("kw:") for n in graph.nodes)
    assert idf_map  # idf map non-empty


def test_graph_with_entities_and_relations():
    chunks = _chunks()
    ents = [Entity(id="ent:portland", name="Portland", type="place")]
    relations = [{"source": "Alex Carter", "relation": "lives_in", "target": "Portland"}]
    graph, _ = build_graph(chunks, entities=ents, relations=relations)
    ent_ids = [n.id for n in graph.nodes]
    assert "ent:portland" in ent_ids
    kinds = {e.kind for e in graph.edges}
    assert "rel" in kinds


def test_communities_and_save_load_roundtrip(tmp_path):
    chunks = _chunks()
    graph, _ = build_graph(chunks)
    detect_communities(graph)
    assert graph.communities  # Louvain ran and labeled nodes

    p = tmp_path / "graph.json"
    save_graph(graph, p)
    loaded = load_graph(p)
    assert loaded is not None
    assert len(loaded.nodes) == len(graph.nodes)
    assert len(loaded.edges) == len(graph.edges)


def test_save_graph_missing_returns_empty_graph(tmp_path):
    from digital_twin.models import GraphData
    assert load_graph(tmp_path / "nope.json") == GraphData()