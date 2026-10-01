"""Regression checks for repeated model loading and slow LLM failure paths."""
from types import SimpleNamespace
import httpx
import openai
import pytest
from digital_twin.config import Config
from digital_twin import laya_agent, llm


def test_laya_weights_shared_across_engines(monkeypatch):
    calls = []
    agent = object()
    monkeypatch.setitem(__import__("sys").modules, "laya", SimpleNamespace(
        load=lambda *args, **kwargs: calls.append(kwargs) or agent))
    laya_agent._cached_agent.cache_clear()
    try:
        a = laya_agent.LayaEngine(device="cuda")
        b = laya_agent.LayaEngine(device="cuda")
        assert a._load() is b._load() is agent
        assert calls == [{"device": "cuda", "subfolder": "typed-decisions"}]
    finally:
        laya_agent._cached_agent.cache_clear()


def client(monkeypatch, create):
    cfg = Config(llm_api_key="test", llm_api_key_2=None, llm_enabled=True,
                 llm_model="primary", llm_fallback_model="fallback",
                 llm_timeout=4, llm_attempt_timeout=2)
    slot = llm._Slot("test", "http://test", 4, 40)
    slot._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm, "_slot_for", lambda *args: slot)
    return llm.ChatClient(cfg)


def response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_retired_primary_goes_straight_to_fallback(monkeypatch):
    models = []
    def create(**kwargs):
        models.append(kwargs["model"])
        if kwargs["model"] == "primary":
            raise openai.NotFoundError("retired", response=httpx.Response(
                404, request=httpx.Request("POST", "http://test")), body={})
        return response('{"answer":"ok"}')
    c = client(monkeypatch, create)
    assert c.complete_json([])["answer"] == "ok"
    assert models == ["primary", "fallback"]
    assert c.last_model == "fallback"


def test_auth_failure_is_not_retried(monkeypatch):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        raise openai.AuthenticationError("bad key", response=httpx.Response(
            401, request=httpx.Request("POST", "http://test")), body={})
    c = client(monkeypatch, create)
    with pytest.raises(llm.LLMUnavailable):
        c.complete([])
    assert len(calls) == 1


def test_deadline_includes_retries_and_json_format_retry(monkeypatch):
    clock = [0.0]
    timeouts = []
    monkeypatch.setattr(llm.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(llm.time, "sleep", lambda n: clock.__setitem__(0, clock[0]+n))
    def create(**kwargs):
        timeouts.append(kwargs["timeout"])
        clock[0] += kwargs["timeout"]
        raise openai.APITimeoutError(request=httpx.Request("POST", "http://test"))
    c = client(monkeypatch, create)
    with pytest.raises(llm.LLMUnavailable):
        c.complete_json([])
    assert clock[0] == 4
    assert timeouts == [2, 1]


def test_nemotron_thinking_disabled_and_timeout_passed(monkeypatch):
    calls=[]
    c=client(monkeypatch, lambda **kw: calls.append(kw) or response("ok"))
    c.cfg.llm_model="nvidia/nemotron-3.5-lightning-30b-a3b"
    assert c.complete([]) == "ok"
    assert calls[0]["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert 0 < calls[0]["timeout"] <= 2


def test_empty_answers_not_success(monkeypatch):
    c=client(monkeypatch, lambda **kw: response(None))
    monkeypatch.setattr(llm.time, "sleep", lambda n: None)
    with pytest.raises(llm.LLMUnavailable, match="empty response"):
        c.complete_json([])


def test_stream_skips_repeated_primary_and_backoff(monkeypatch):
    calls = []
    sleeps = []
    class Stream:
        def __iter__(self):
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='{"answer":"ok"}'))])
        def close(self):
            pass
    def create(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == "primary":
            raise openai.APITimeoutError(request=httpx.Request("POST", "http://test"))
        return Stream()
    c = client(monkeypatch, create)
    previews = []
    c.on_text = previews.append
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    assert c.complete_json([])["answer"] == "ok"
    assert calls == ["primary", "fallback"]
    assert not sleeps
    assert previews == ["", '{"answer":"ok"}']


def test_keys_alternate_across_new_request_clients(monkeypatch):
    monkeypatch.setattr(llm, "_IRR", 0)
    cfg = Config(llm_api_key="key-one", llm_api_key_2="key-two", llm_rpm=40)
    starts = [llm.ChatClient(cfg)._ordered_slots()[0] for _ in range(6)]
    assert starts == [0, 1, 0, 1, 0, 1]


def test_strict_rolling_minute_limit_is_independent_per_key(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(llm.time, "monotonic", lambda: clock[0])
    first, second = llm._TokenBucket(40), llm._TokenBucket(40)
    assert all(first.take() == 0 for _ in range(40))
    assert first.take() == 60
    assert second.take() == 0
    clock[0] = 30
    assert first.take() == 30
    clock[0] = 60
    assert first.take() == 0


def test_json_format_retry_counts_as_an_http_attempt(monkeypatch):
    calls=[]
    def create(**kwargs):
        calls.append(kwargs)
        if len(calls)==1:
            raise openai.BadRequestError("unsupported format",response=httpx.Response(
                400,request=httpx.Request("POST","http://test")),body={})
        return response('{"answer":"ok"}')
    c=client(monkeypatch,create)
    assert c.complete_json([])["answer"] == "ok"
    assert len(c._slots[0].bucket.requests) == 2


def test_gpt_oss_uses_low_reasoning_effort(monkeypatch):
    calls=[]
    c=client(monkeypatch, lambda **kw:calls.append(kw) or response("ok"))
    c.cfg.llm_model="openai/gpt-oss-20b"
    assert c.complete([])=="ok"
    assert calls[0]["reasoning_effort"]=="low"


def test_stream_retries_same_model_on_other_key_without_dead_fallback(monkeypatch):
    cfg=Config(llm_api_key="first",llm_api_key_2="second",llm_enabled=True,
               llm_model="openai/gpt-oss-20b",llm_fallback_model="",llm_timeout=4)
    calls=[]
    class Stream:
        def __iter__(self):
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='{"answer":"ok"}'))])
        def close(self):pass
    def slot_for(cfg,key):
        slot=llm._Slot(key,"http://test",4,40)
        def create(**kwargs):
            calls.append((key,kwargs["model"]))
            if key=="first":raise openai.APITimeoutError(request=httpx.Request("POST","http://test"))
            return Stream()
        slot._client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        return slot
    monkeypatch.setattr(llm,"_slot_for",slot_for)
    monkeypatch.setattr(llm,"_IRR",0)
    c=llm.ChatClient(cfg);c.on_text=lambda text:None
    assert c.complete_json([])["answer"]=="ok"
    assert calls==[("first","openai/gpt-oss-20b"),("second","openai/gpt-oss-20b")]


def test_stream_attempt_deadline_includes_reasoning_chunks(monkeypatch):
    clock = [0.0]
    closed = []
    class Stream:
        def __iter__(self):
            clock[0] = 3.0
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))])
        def close(self):
            closed.append(True)
    c = client(monkeypatch, lambda **kw: Stream())
    c.cfg.llm_fallback_model = ""
    c.on_text = lambda text: None
    monkeypatch.setattr(llm.time, "monotonic", lambda: clock[0])
    with pytest.raises(llm.LLMUnavailable, match="deadline"):
        c.complete_text("fictional question")
    assert closed == [True]
