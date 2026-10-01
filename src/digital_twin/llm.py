"""OpenAI-compatible chat client used for extraction, community summaries,
persona writing and final answer reasoning. Works with OpenAI, NVIDIA NIM
(integrate.api.nvidia.com/v1), Ollama, vLLM, LM Studio...

Up to two API keys are supported and load-balanced:
- requests are round-robined across the keys;
- each key has a strict rolling-minute `DIGITAL_TWIN_LLM_RPM` limit;
- transient failures are retried against the other key; authentication fails fast.

Slot state (clients, rate buckets, round-robin counter) lives at module level
so it survives the per-request engine instances the server creates."""

from __future__ import annotations

import json
import logging
import re
from collections import deque
import threading
import time
from typing import Any

from .config import Config
from .text_utils import tokens

log = logging.getLogger(__name__)

_ICLOCK = threading.Lock()
_IRR = 0  # global round-robin cursor
_POOL: dict[tuple[str, str, float, float], "_Slot"] = {}
_POOL_LOCK = threading.Lock()
_MAX_ATTEMPTS = 3  # overall attempts including retries/failover


class LLMUnavailable(Exception):
    """Raised when no API key is configured or every key attempt failed."""


def _is_retired(err: Exception) -> bool:
    """Models that are gone (404/410) should trigger the fallback model."""
    try:
        import openai as _oa
    except Exception:  # noqa: BLE001
        return False
    if isinstance(err, _oa.APIStatusError):
        return err.status_code in (404, 410)
    return False


def _retryable(err: Exception) -> bool:
    """Transient/network errors are worth retrying; auth/not-found/410 are not."""
    try:
        import openai as _oa
    except Exception:  # noqa: BLE001
        return True
    if isinstance(err, (_oa.APIConnectionError, _oa.APITimeoutError)):
        return True
    if isinstance(err, _oa.APIStatusError):
        return err.status_code in (408, 409, 429, 500, 502, 503, 504)
    return True


class _TokenBucket:
    """Strict per-key rolling-minute request limiter (failed calls count too)."""

    def __init__(self, rpm: float):
        self.cap = max(int(rpm), 1)
        self.requests = deque()
        self.lock = threading.Lock()

    def take(self) -> float:
        with self.lock:
            now = time.monotonic()
            while self.requests and self.requests[0] <= now - 60:
                self.requests.popleft()
            if len(self.requests) >= self.cap:
                return max(0.0, 60 - (now - self.requests[0]))
            self.requests.append(now)
            return 0.0


class _Slot:
    """One API key: client + rate bucket."""

    __slots__ = ("key", "base_url", "timeout", "bucket", "_client")

    def __init__(self, key: str, base_url: str, timeout: float, rpm: float):
        self.key = key
        self.base_url = base_url
        self.timeout = timeout
        self.bucket = _TokenBucket(rpm)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.key,
                base_url=self.base_url or None,
                timeout=self.timeout,
                max_retries=0,  # retries/failover handled by ChatClient.complete
            )
        return self._client


def _slot_for(cfg: Config, key: str) -> _Slot:
    cache_key = (cfg.llm_base_url, key, cfg.llm_rpm, cfg.llm_timeout)
    with _POOL_LOCK:
        slot = _POOL.get(cache_key)
        if slot is None:
            slot = _Slot(key, cfg.llm_base_url, cfg.llm_timeout, cfg.llm_rpm)
            _POOL[cache_key] = slot
        return slot


def _bounded(text: str, budget: int) -> str:
    """Keep at most `budget` (approx) tokens of prose, front-loaded."""
    if budget <= 0:
        return ""
    toks = tokens(text or "")
    if len(toks) <= budget:
        return text
    return " ".join(toks[:budget])


class ChatClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.last_model: str | None = None
        self.on_text = None
        self._slots = [_slot_for(cfg, key) for key in cfg.llm_keys]

    # -------------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return bool(self._slots) and self.cfg.llm_enabled

    @property
    def available(self) -> bool:
        """Alias used by graphrag/_summarize_community to gate LLM summaries."""
        return self.enabled

    def _ordered_slots(self) -> list[int]:
        """Round-robin: [next] followed by the remaining keys."""
        n = len(self._slots)
        if n == 0:
            return []
        with _ICLOCK:
            global _IRR
            start = _IRR % n
            _IRR += 1
        return [start] + [i for i in range(n) if i != start]

    # -------------------------------------------------------------------------
    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.4,
                 max_tokens: int = 900, json_mode: bool = False) -> str:
        if not self.enabled:
            raise LLMUnavailable("no LLM key configured (OPENAI_API_KEY/OPENAI_API_KEY_2)")
        deadline = time.monotonic() + max(self.cfg.llm_timeout, 0.01)
        last_err: Exception | None = None
        primary_slots = self._ordered_slots()
        if self.on_text is not None and self.cfg.llm_fallback_model:
            # Switch model and key together rather than queue on the same model twice.
            attempts = [(self.cfg.llm_model, primary_slots[0]),
                        (self.cfg.llm_fallback_model, primary_slots[-1])]
        else:
            attempts = [(self.cfg.llm_model, primary_slots[i % len(primary_slots)])
                        for i in range(len(primary_slots) if self.on_text is not None else _MAX_ATTEMPTS)]
            if self.cfg.llm_fallback_model:
                attempts += [(self.cfg.llm_fallback_model, i) for i in primary_slots]
        retired_models: set[str] = set()
        for attempt, (model, idx) in enumerate(attempts):
            if model in retired_models:
                continue
            slot = self._slots[idx]
            try:
                text = self._call(slot, model, messages, temperature, max_tokens,
                                  json_mode, deadline=deadline)
                self.last_model = model
                return text
            except Exception as err:
                last_err = err
                if _is_retired(err):
                    retired_models.add(model)
                elif not _retryable(err):
                    raise LLMUnavailable(str(err)) from err
                log.warning("LLM attempt %d failed (%s): %s", attempt + 1, model, err)
                if self.on_text is None and _retryable(err) and attempt + 1 < len(attempts):
                    time.sleep(min(2 ** min(attempt, 3), max(0, deadline - time.monotonic())))
        raise LLMUnavailable(str(last_err) if last_err else "LLM call failed")

    def _call(self, slot: "_Slot", model: str, messages: list[dict[str, str]],
              temperature: float, max_tokens: int, json_mode: bool,
              *, deadline: float | None = None) -> str:
        started = time.monotonic()
        attempt_deadline = min(deadline or float("inf"), started + self.cfg.llm_attempt_timeout)
        kwargs: dict[str, Any] = dict(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
        )
        if "gpt-oss" in model.lower():
            kwargs["reasoning_effort"] = "low"
        if "nemotron" in model.lower():
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": self.cfg.llm_thinking}
            }
        if self.on_text is not None:
            kwargs["stream"] = True
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        def request():
            # Every HTTP attempt, including JSON-format retries, uses quota.
            while True:
                remaining = attempt_deadline - time.monotonic()
                if remaining <= 0:
                    raise LLMUnavailable("LLM response deadline exceeded")
                wait = slot.bucket.take()
                if not wait:
                    break
                if self.on_text is not None:
                    raise LLMUnavailable("This API key is at its request limit; trying the alternate slot")
                time.sleep(min(wait + 0.01, remaining))
            resp = slot.client.chat.completions.create(
                **kwargs, timeout=min(self.cfg.llm_attempt_timeout, remaining)
            )
            if self.on_text is None:
                return resp
            from types import SimpleNamespace
            content = ""
            self.on_text(content)  # clear any abandoned attempt's preview
            try:
                for chunk in resp:
                    if time.monotonic() >= attempt_deadline:
                        raise LLMUnavailable("LLM response deadline exceeded")
                    if chunk.choices:
                        content += chunk.choices[0].delta.content or ""
                        self.on_text(content)
            finally:
                resp.close()
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=content))])

        try:
            resp = request()
        except Exception as err:
            from openai import APIStatusError
            if (json_mode and isinstance(err, APIStatusError)
                    and err.status_code in (400, 422)):
                kwargs.pop("response_format", None)
                resp = request()
            else:
                # Keep provider exception types for auth/retirement/retry classification.
                raise
        text = resp.choices[0].message.content or ""
        if not text.strip() and "response_format" in kwargs:
            kwargs.pop("response_format")
            resp = request()
            text = resp.choices[0].message.content or ""
        if not text.strip():
            raise LLMUnavailable("empty response from LLM")
        log.info("LLM reply model=%s input_chars=%d output_chars=%d elapsed_ms=%d",
                 model, sum(len(m.get("content", "")) for m in messages), len(text),
                 round((time.monotonic() - started) * 1000))
        return text

    def complete_text(self, prompt: str, *, system: str | None = None,
                      temperature: float = 0.3, max_tokens: int = 900) -> str:
        msgs: list[dict[str, str]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return self.complete(msgs, temperature=temperature, max_tokens=max_tokens)

    def complete_json(self, messages: list[dict[str, str]], *, temperature: float = 0.2,
                      max_tokens: int = 1400) -> Any:
        text = self.complete(messages, temperature=temperature, max_tokens=max_tokens,
                             json_mode=True)
        return _parse_json(text)

    # -------------------------------------------------------------------------
    # structured extraction over one document
    # -------------------------------------------------------------------------
    def extract(self, doc_text: str, title: str = "") -> dict[str, Any]:
        """Extract entities, relationships, preferences and decision patterns
        from one document. Returns a dict with keys: entities, relations,
        preferences, decision_patterns, facts, name_guess."""
        if not self.enabled:
            return {}
        sys = (
            "You extract structured facts about ONE person from their own "
            "writing. Be literal - only use what is written. JSON only."
        )
        budget = max(512, self.cfg.llm_context_tokens - 4096)
        user = f"""Title: {title or 'untitled'}

Text:
{_bounded(doc_text, budget)}

Return a JSON object with exactly these keys:
  "name_guess": string or empty - the person's own name if stated
  "entities": [{{"name": string, "type": "person|place|org|thing|concept|skill|food|activity", "note": string}}]
      - people, places, projects, foods, activities, skills, things mentioned (max 15)
  "relations": [{{"source": string, "relation": string, "target": string}}]
      - factual links like works_at, lives_in, prefers, friends_with (max 10)
  "preferences": [{{"domain": string, "stance": "positive|negative|neutral",
      "statement": string, "strength": 0.0-1.0, "examples": [string]}}]
      - explicit likes/dislikes (max 8)
  "decision_patterns": [{{"name": string, "trigger": string, "behavior": string,
      "examples": [string]}}]
      - how they decide: tradeoffs, defaults, rules (max 6)
  "facts": [{{"text": string, "category": "preference|decision|value|identity|habit|note"}}]
      - short atomic statements about them (max 12)

If a key has nothing, use an empty list. Do not invent names or facts."""
        try:
            data = self.complete_json(
                [{"role": "system", "content": sys}, {"role": "user", "content": user}],
                temperature=0.1, max_tokens=1600)
        except Exception as e:  # noqa: BLE001
            log.warning("extraction failed: %s", e)
            return {}
        return data if isinstance(data, dict) else {}

    # -------------------------------------------------------------------------
    # community summary (used by graphrag when llm passed in)
    # -------------------------------------------------------------------------
    # (graphrag calls llm.complete_text directly)


def _parse_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}