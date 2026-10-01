"""End-to-end LLM-path tests against a local mock OpenAI-compatible server.

Exercises extraction, persona writing, community summaries and final reasoning
without needing network access or an API key."""
import pytest

from mocks import mock_llm
from digital_twin.engine import Twin
from digital_twin.profile import load_profile


@pytest.fixture
def mock_server(tmp_path):
    mock_llm.set_log_path(str(tmp_path / "intents.log"))
    srv = mock_llm.start(port=0)
    port = srv.server_address[1]
    yield port
    srv.shutdown()
    srv.server_close()


def _enable_llm(cfg, port):
    cfg.llm_api_key = "sk-mock"
    cfg.llm_base_url = f"http://127.0.0.1:{port}/v1"
    cfg.llm_model = "mock-gpt"
    cfg.llm_enabled = True


def test_build_with_llm_routes_all_calls(mock_cfg, mock_server, demo_raw):
    from digital_twin.pipeline import build

    _enable_llm(mock_cfg, mock_server)
    res = build(mock_cfg, raw_dir=demo_raw, use_llm=True)
    assert res.llm_used is True

    ints = mock_llm.intents()
    assert ints.get("extract", 0) == 6      # one per document
    assert ints.get("persona", 0) == 1
    assert ints.get("community", 0) >= 1    # LLM community summaries now run

    prof = load_profile(mock_cfg.profile_path)
    assert prof is not None
    assert prof.name == "Alex Carter"       # recovered via extraction + merge
    assert "two-week" in (prof.persona or "")  # written by the LLM route


def test_ask_with_llm_produces_first_person_choice(mock_cfg, mock_server, demo_raw):
    from digital_twin.pipeline import build

    _enable_llm(mock_cfg, mock_server)
    build(mock_cfg, raw_dir=demo_raw, use_llm=True)

    opts = ["Buy a flagship 16-inch now",
            "Get a certified refurbished 14-inch with a 3-year warranty"]
    ans = Twin(mock_cfg).ask("New laptop?", options=opts)

    assert mock_llm.intents().get("reason", 0) >= 1
    assert ans.choice == opts[1]            # mock reason picks refurb, matched to option
    assert "refurbished" in (ans.answer or "").lower()
    assert ans.reasoning
    assert ans.model == "mock-gpt"
    assert ans.meta["llm_used"] is True
    assert abs(ans.confidence - (0.6 * 0.8)) < 1e-6  # 0.4*Laya term absent (Laya off)


def test_llm_down_falls_back_to_template(mock_cfg, demo_raw):
    """A dead endpoint must not crash the pipeline; it degrades like no-LLM."""
    from digital_twin.pipeline import build

    mock_cfg.llm_base_url = "http://127.0.0.1:1/v1"  # guaranteed refused port
    mock_cfg.llm_api_key = "sk-broken"
    mock_cfg.llm_enabled = True
    res = build(mock_cfg, raw_dir=demo_raw, use_llm=True)
    assert res.llm_used is False  # reconnect failures surface as LLMUnavailable -> offline
    prof = load_profile(mock_cfg.profile_path)
    assert prof is not None
    assert prof.name != "Alex Carter"