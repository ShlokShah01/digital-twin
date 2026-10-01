"""Engine ask() paths without any model: no Laya, no LLM."""
import pytest

from digital_twin.engine import Twin
from digital_twin.llm import LLMUnavailable


def test_ask_with_options_no_models(built_twin_cfg):
    cfg, res, prof = built_twin_cfg
    twin = Twin(cfg)
    assert twin.load()

    ans = twin.ask(
        "Should I buy a flagship laptop or a refurbished one?",
        options=["Buy a flagship now",
                 "Get a certified refurbished with warranty",
                 "Wait a month"])
    assert ans.question
    # without Laya there is no vote: every option shows probability 0.0
    assert ans.choices and all(c.probability == 0.0 for c in ans.choices)
    assert ans.choice is None
    assert ans.confidence == 0.0
    assert ans.answer           # template answer still produced
    assert ans.reasoning
    assert len(ans.sources) > 0
    assert ans.model == "template"
    assert ans.meta["llm_used"] is False
    assert ans.meta["laya_used"] is False


def test_ask_open_question_no_models(built_twin_cfg):
    cfg, res, prof = built_twin_cfg
    twin = Twin(cfg)
    ans = twin.ask("What would I do on a Friday evening?")
    assert ans.question
    assert ans.answer
    assert ans.sources


def test_ask_empty_question_rejected(built_twin_cfg):
    cfg, res, prof = built_twin_cfg
    with pytest.raises(ValueError):
        Twin(cfg).ask("   ")


def test_ask_before_build_raises(cfg):
    twin = Twin(cfg)
    with pytest.raises(RuntimeError):
        twin.ask("anything")


def test_single_option_is_not_a_contest(built_twin_cfg):
    """One option must not decay into a meaningless P(true)=1 vote."""
    cfg, res, prof = built_twin_cfg
    ans = Twin(cfg).ask("Get the refurb?", options=["Only this one option"])
    assert ans.choice is None
    assert ans.confidence == 0.0
    assert all(c.probability == 0.0 for c in ans.choices)


# --- ensemble agreement / conflict (stubbed Laya + stubbed LLM) --------------

def _stub_laya(twin, probs, noul, choice_probs):
    twin.laya.predict_choice = lambda brief, opts: {
        "noul": noul, "probabilities": probs, "choice_probs": choice_probs}


class _StubLLM:
    enabled = True

    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, messages, **kw):
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


def _stub_llm(twin, payload):
    twin.llm = _StubLLM(payload)


def test_ensemble_agreement_lifts_confidence(built_twin_cfg):
    cfg, _, _ = built_twin_cfg
    twin = Twin(cfg)
    assert twin.load()
    opts = ["Option A", "Option B"]
    _stub_laya(twin, {"Option A": 0.45, "Option B": 0.55},
               {"Option A": 0.4, "Option B": 0.6},
               {"Option A": 0.5, "Option B": 0.5})
    _stub_llm(twin, {"reasoning": "I prefer B.", "best": "Option B",
                     "confidence": 0.9, "answer": "I would pick B."})
    ans = twin.ask("Which option?", options=opts)
    assert ans.choice == "Option B"
    assert ans.model == cfg.llm_model
    assert ans.meta["llm_used"] is True
    assert ans.meta["llm_enabled"] is True
    assert ans.meta["resolution"] == "agreement"
    # Laya ensemble confidence is 0.525 (mean of the two heads), so:
    # 0.6 * 0.9 + 0.4 * 0.525 = 0.75
    assert abs(ans.confidence - 0.75) < 1e-6
    assert any(c.probability > 0.5 for c in ans.choices)


def test_ensemble_conflict_lowers_confidence(built_twin_cfg):
    cfg, _, _ = built_twin_cfg
    twin = Twin(cfg)
    assert twin.load()
    opts = ["Option A", "Option B"]
    _stub_laya(twin, {"Option A": 0.45, "Option B": 0.55},
               {"Option A": 0.4, "Option B": 0.6},
               {"Option A": 0.5, "Option B": 0.5})
    _stub_llm(twin, {"reasoning": "I prefer A.", "best": "Option A",
                     "confidence": 0.9, "answer": "I would pick A."})
    ans = twin.ask("Which option?", options=opts)
    assert ans.choice == "Option A"          # LLM prevails on conflict
    assert ans.meta["resolution"] == "conflict"
    assert "trusting the reasoned read" in ans.reasoning
    assert abs(ans.confidence - 0.6 * 0.9) < 1e-6


def test_llm_failure_keeps_laya_signals(built_twin_cfg):
    """LLM configured but down: degrade to the template, keep the calibrated
    Laya probabilities in the answer, and report llm_used=False honestly."""
    cfg, _, _ = built_twin_cfg
    twin = Twin(cfg)
    assert twin.load()
    opts = ["Option A", "Option B"]
    _stub_laya(twin, {"Option A": 0.45, "Option B": 0.55},
               {"Option A": 0.4, "Option B": 0.6},
               {"Option A": 0.5, "Option B": 0.5})
    _stub_llm(twin, LLMUnavailable("connection refused"))
    ans = twin.ask("Which option?", options=opts)
    assert ans.model == "template"
    assert ans.meta["llm_used"] is False
    assert ans.meta["llm_enabled"] is True
    assert ans.meta["resolution"] == "laya_only"
    assert "strongest signal" in ans.answer
    assert max(c.probability for c in ans.choices) > 0.5


def test_llm_garbage_falls_back(built_twin_cfg):
    cfg, _, _ = built_twin_cfg
    twin = Twin(cfg)
    assert twin.load()
    opts = ["Option A", "Option B"]
    _stub_llm(twin, "definitely not json")
    ans = twin.ask("Which option?", options=opts)
    assert ans.model == "template"
    assert ans.meta["llm_used"] is False
    assert ans.meta["resolution"] in ("none", "laya_only")

@pytest.mark.parametrize("question", ["HELLO", "hlo", "Hi!"])
def test_greetings_do_not_retrieve_or_call_model(cfg, monkeypatch, question):
    twin = Twin(cfg)
    def unexpected(*args, **kwargs):
        raise AssertionError("A greeting must not load private evidence or call a model")
    monkeypatch.setattr(twin, "ensure_built", unexpected)
    monkeypatch.setattr(twin.llm, "complete_json", unexpected)
    answer = twin.ask(question)
    assert answer.answer == "Hi! How can I help?"
    assert not answer.sources and not answer.reasoning
    assert not answer.meta["llm_used"]


def test_identity_is_instant_without_retrieval(cfg, monkeypatch):
    twin = Twin(cfg)
    monkeypatch.setattr(twin, "ensure_built", lambda: pytest.fail("identity needs no retrieval"))
    answer = twin.ask("WHO ARE YOU")
    assert "digital twin" in answer.answer and answer.model == "identity"


def test_chat_failure_does_not_claim_keys_are_missing(built_twin_cfg, monkeypatch):
    twin = Twin(built_twin_cfg[0])
    twin.llm = _StubLLM({})
    twin.llm.on_text = None
    def fail(*args, **kwargs):
        raise LLMUnavailable("provider timeout")
    twin.llm.complete_text = fail
    with pytest.raises(LLMUnavailable, match="temporarily unavailable"):
        twin.ask("Tell me about warranties")


def test_plain_chat_streams_answer_without_decision_report(built_twin_cfg):
    import json
    twin = Twin(built_twin_cfg[0])
    twin.llm = _StubLLM({})
    previews = []
    calls = []
    def complete_text(prompt, **kwargs):
        calls.append((prompt, kwargs))
        twin.llm.on_text("A clear reply.")
        return "A clear reply."
    twin.llm.complete_text = complete_text
    answer = twin.ask("Explain warranties", on_text=previews.append)
    assert answer.answer == "A clear reply." and answer.meta["llm_used"]
    assert not answer.reasoning
    assert json.loads(previews[-1])["answer"] == answer.answer
    assert "Return JSON" not in calls[0][0]
    assert twin.llm.on_text == previews.append
