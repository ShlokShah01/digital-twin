"""API contract tests via FastAPI's TestClient.

One app import serves all tests; each test points `server._cfg` at the Config
it wants (a session-built twin or a fresh, unbuilt Config). Index/asset routes
exercise the real web/dist bundle because the repo ships a built React app.
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

import digital_twin.server as srv
from mocks import mock_llm

client = TestClient(srv.app)


@pytest.fixture
def built_cfg(built_twin_cfg):
    srv._cfg = built_twin_cfg[0]
    return built_twin_cfg[0]


def test_health_built(built_cfg):
    r = client.get("/api/health")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["twin_built"] is True
    assert j["chunks"] > 0
    assert j["llm"] is False


def test_profile_built(built_cfg):
    r = client.get("/api/profile")
    assert r.status_code == 200
    j = r.json()
    assert j["name"]
    assert j["stats"]["n_chunks"] > 0
    assert j["stats"]["n_documents"] > 0
    assert isinstance(j["preferences"], list)
    assert isinstance(j["decision_patterns"], list)
    assert isinstance(j["style"], dict)


def test_graph_built(built_cfg):
    r = client.get("/api/graph")
    assert r.status_code == 200
    j = r.json()
    assert j["built"] is True
    assert j["stats"]["communities"] > 0
    assert any(n["kind"] == "entity" for n in j["nodes"])
    assert all("label" in n for n in j["nodes"])


def test_ask_offline_with_options(built_cfg):
    r = client.post("/api/ask", json={
        "question": "Should I buy a flagship laptop or a refurbished one?",
        "options": ["Buy a flagship now",
                    "Get a certified refurbished with warranty",
                    "Wait a month"],
    })
    assert r.status_code == 200
    j = r.json()
    assert j["question"]
    assert j["answer"]
    assert j["model"] == "template"
    assert j["meta"]["llm_used"] is False
    assert j["meta"]["llm_enabled"] is False
    assert j["meta"]["resolution"] == "none"
    assert len(j["sources"]) > 0
    assert j["sources"][0]["snippet"]


def test_ask_blank_question_400(built_cfg):
    r = client.post("/api/ask", json={"question": "   "})
    assert r.status_code == 400


def test_ask_missing_twin_400(cfg):
    srv._cfg = cfg
    assert client.get("/api/health").json()["twin_built"] is False
    r = client.post("/api/ask", json={"question": "anything"})
    assert r.status_code == 400


def test_profile_missing_404(cfg):
    srv._cfg = cfg
    assert client.get("/api/profile").status_code == 404


def test_graph_unbuilt_returns_empty(cfg):
    srv._cfg = cfg
    r = client.get("/api/graph")
    assert r.status_code == 200
    j = r.json()
    assert j["built"] is False
    assert j["clusters"] == []


def test_build_bad_data_dir_400(cfg, tmp_path):
    srv._cfg = cfg
    r = client.post("/api/build", json={"data": str(tmp_path / "missing")})
    assert r.status_code == 400


def test_ingest_missing_file_400(cfg, tmp_path):
    srv._cfg = cfg
    r = client.post("/api/ingest", json={"path": str(tmp_path / "nope.txt")})
    assert r.status_code == 400


def test_index_serves_web_app(built_cfg):
    r = client.get("/")
    assert r.status_code == 200
    assert '<div id="root">' in r.text


def test_ask_with_mock_llm_via_api(built_twin_cfg):
    """Full wiring: HTTP POST -> Twin.ask -> ChatClient -> mock LLM -> first-
    person answer. Proves the LLM path works end-to-end through the server."""
    cfg = copy.deepcopy(built_twin_cfg[0])
    ml = mock_llm.start(port=0)
    port = ml.server_address[1]
    try:
        cfg.llm_api_key = "sk-mock"
        cfg.llm_base_url = f"http://127.0.0.1:{port}/v1"
        cfg.llm_model = "mock-gpt"
        cfg.llm_enabled = True
        srv._cfg = cfg
        opts = ["Buy a flagship 16-inch now",
                "Get a certified refurbished 14-inch with a 3-year warranty"]
        r = client.post("/api/ask", json={"question": "New laptop?", "options": opts})
        assert r.status_code == 200
        j = r.json()
        assert mock_llm.intents().get("reason", 0) >= 1
        assert j["choice"] == opts[1]
        assert j["model"] == "mock-gpt"
        assert j["meta"]["llm_used"] is True
        assert j["meta"]["llm_enabled"] is True
        assert j["meta"]["resolution"] == "llm_only"
        assert abs(j["confidence"] - (0.6 * 0.8)) < 1e-6
    finally:
        ml.shutdown()
        ml.server_close()

def test_stream_answer_with_local_provider(built_twin_cfg):
    import json
    cfg = copy.deepcopy(built_twin_cfg[0])
    ml = mock_llm.start(port=0)
    try:
        cfg.llm_api_key = "sk-mock"
        cfg.llm_base_url = f"http://127.0.0.1:{ml.server_address[1]}/v1"
        cfg.llm_model = "mock-gpt"
        cfg.llm_enabled = True
        srv._cfg = cfg
        response = client.post("/api/ask/stream", json={"question": "New laptop?"})
        assert response.status_code == 200
        events = [json.loads(line) for line in response.text.splitlines()]
        assert events[0]["type"] == "status"
        previews = [e["data"] for e in events if e["type"] == "text"]
        assert len(previews) > 2
        assert json.loads(previews[-1])["answer"] == mock_llm.REASON["answer"]
        assert events[-1]["type"] == "answer"
        answer = events[-1]["data"]
        assert answer["answer"] == mock_llm.REASON["answer"]
        assert answer["sources"] and answer["meta"]["llm_used"]
        assert answer["meta"]["timing_ms"]["generation"] >= 0
    finally:
        ml.shutdown()
        ml.server_close()


def test_stream_error_and_validation(cfg):
    import json
    srv._cfg = cfg
    assert client.post("/api/ask/stream", json={"question": "   "}).status_code == 400
    response = client.post("/api/ask/stream", json={"question": "anything"})
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1]["type"] == "error"
    assert "No digital twin built" in events[-1]["data"]


def test_provider_failure_is_retryable_error_not_false_answer(cfg, monkeypatch):
    import json
    from digital_twin.llm import LLMUnavailable
    class UnavailableTwin:
        def ask(self, *args, **kwargs):
            raise LLMUnavailable("The answer service is temporarily unavailable. Please retry.")
    monkeypatch.setattr(srv, "_twin", UnavailableTwin)
    response = client.post("/api/ask", json={"question": "Explain warranties"})
    assert response.status_code == 503
    response = client.post("/api/ask/stream", json={"question": "Explain warranties"})
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1]["type"] == "error"
    assert "temporarily unavailable" in events[-1]["data"]
    assert not any(e["type"] == "answer" for e in events)
