"""Offline build pipeline over the shared session twin + incremental add_source."""
from digital_twin.profile import load_profile


def test_offline_build_creates_full_artifacts(built_twin_cfg):
    cfg, res, prof = built_twin_cfg
    assert res.llm_used is False
    assert res.n_documents == 6
    assert res.n_chunks >= 5
    assert res.n_facts > 0
    assert res.n_entities > 0
    assert res.n_nodes > 0
    assert res.n_communities > 0
    assert cfg.graph_path.exists()
    assert cfg.profile_path.exists()
    assert cfg.index_path.exists()
    assert cfg.community_path.exists()


def test_built_profile_shape(built_twin_cfg):
    cfg, res, prof = built_twin_cfg
    assert prof is not None
    assert prof.persona
    assert prof.preferences  # heuristic mining pulled real rules
    assert prof.decision_patterns
    assert prof.style.n_words > 0
    assert prof.stats["n_chunks"] == res.n_chunks
    assert prof.guardrails


def test_profile_roundtrip_via_load(built_twin_cfg):
    cfg, res, prof = built_twin_cfg
    again = load_profile(cfg.profile_path)
    assert again is not None
    assert again.name == prof.name
    assert again.persona == prof.persona


def test_incremental_add_source_dedupes(cfg, demo_raw):
    from digital_twin.pipeline import add_source, build
    from digital_twin.vector_store import VectorStore

    build(cfg, raw_dir=demo_raw, use_llm=False)
    store = VectorStore(cfg.lancedb_path, dim=384)
    before = store.count()

    new_file = demo_raw / "extra.txt"
    new_file.write_text(
        "Incremental test. I prefer refurbished electronics with a full "
        "warranty and always apply the two-week wait rule.", encoding="utf-8")

    first = add_source(cfg, new_file)
    assert first["chunks_added"] >= 1
    assert store.count() == before + first["chunks_added"]

    second = add_source(cfg, new_file)
    assert second["chunks_added"] == 0  # text-hash dedupe
    assert store.count() == before + first["chunks_added"]