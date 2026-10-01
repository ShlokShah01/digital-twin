"""Shared fixtures: a Config pointed at tmp paths (never the real data/),
generated demo corpus, and a session-wide offline-built twin."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
for p in (SRC, TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from digital_twin.config import Config  # noqa: E402
from digital_twin import demo  # noqa: E402
from digital_twin.llm import ChatClient  # noqa: E402


def make_cfg(tmp: Path, *, llm_off: bool = True, laya_off: bool = True) -> Config:
    c = Config()
    c.root = tmp
    c.raw_dir = tmp / "raw"
    c.twin_dir = tmp / "twin"
    c.raw_dir.mkdir(parents=True, exist_ok=True)
    c.twin_dir.mkdir(parents=True, exist_ok=True)
    # recompute derived paths (they were bound to the default twin_dir at class def)
    c.lancedb_path = c.twin_dir / "lancedb"
    c.graph_path = c.twin_dir / "graph.json"
    c.profile_path = c.twin_dir / "profile.json"
    c.index_path = c.twin_dir / "chunk_index.json"
    c.community_path = c.twin_dir / "communities.json"
    c.llm_api_key_2 = None
    c.llm_timeout = 2
    c.llm_attempt_timeout = 1
    c.llm_api_key = None
    c.llm_enabled = not llm_off
    c.laya_enabled = not laya_off
    return c


@pytest.fixture
def cfg(tmp_path):
    return make_cfg(tmp_path)


@pytest.fixture
def demo_raw(cfg):
    demo.generate(cfg.raw_dir)
    return cfg.raw_dir


@pytest.fixture(scope="session")
def built_twin_cfg(tmp_path_factory):
    """One offline build of the demo corpus, shared across modules (slow: embeds)."""
    from digital_twin.pipeline import build

    base = tmp_path_factory.mktemp("session-twin")
    c = make_cfg(base)
    demo.generate(c.raw_dir)
    res = build(c, raw_dir=c.raw_dir, use_llm=False)
    from digital_twin.profile import load_profile

    prof = load_profile(c.profile_path)
    return c, res, prof


@pytest.fixture
def mock_cfg(tmp_path):
    """Config pointing at the mock LLM server (base URL + port filled by test)."""
    c = make_cfg(tmp_path)
    c.llm_api_key = "sk-mock"
    c.llm_model = "mock-gpt"
    c.llm_enabled = True
    return c