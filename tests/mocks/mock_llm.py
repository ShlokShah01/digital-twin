"""Minimal mock OpenAI /v1/chat/completions server for offline pipeline tests.

Serves the exact endpoint contract the openai SDK client in llm.py talks to,
routing on markers inside the concatenated user message and returning realistic
payloads. Keep this in sync with tests/test_mock_llm.py's expectations.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_lock = threading.Lock()
_intents: dict[str, int] = {}
_log_path: str | None = None

EXTRACT = {
    "name_guess": "Alex Carter",
    "entities": [
        {"name": "Loop Labs", "type": "org", "note": "product design employer"},
        {"name": "Portland", "type": "place", "note": "home city"},
        {"name": "refurbished", "type": "concept", "note": "prefers durable refurbished goods"},
    ],
    "relations": [
        {"source": "Alex Carter", "relation": "works_at", "target": "Loop Labs"},
        {"source": "Alex Carter", "relation": "lives_in", "target": "Portland"},
    ],
    "preferences": [
        {"domain": "purchases", "stance": "positive",
         "statement": "buys refurbished electronics with a full warranty",
         "strength": 0.9, "examples": ["laptop replacement"]},
    ],
    "decision_patterns": [
        {"name": "two-week wait", "trigger": "any purchase over $200",
         "behavior": "waits two weeks and re-evaluates before buying", "examples": ["laptop"]},
    ],
    "facts": [
        {"text": "prefers refurbished goods with a full warranty", "category": "preference"},
        {"text": "writes email over phone calls", "category": "habit"},
    ],
}

PERSONA = (
    "I keep a small circle and guard my attention carefully - I unsubscribed "
    "from three apps this year and I do not chase novelty. When I buy something "
    "durable I run it past two rules: the two-week wait for anything over two "
    "hundred dollars, and the five-year question. Certified refurbished "
    "electronics with a full warranty appeal to me more than flagship products. "
    "I value consistency, craft and reliability over status."
)

COMMUNITY = (
    "This person prefers refurbished, durable goods bought only after a "
    "two-week waiting period. They value consistency and craft over novelty."
)

REASON = {
    "reasoning": "I ran this past my two-week wait and five-year rules. A "
                 "certified refurbished 14-inch with a three-year warranty fits "
                 "both, and my journal says I am willing to buy refurbished.",
    "best": "Get a certified refurbished 14-inch with a 3-year warranty",
    "confidence": 0.8,
    "answer": "I would get the certified refurbished 14-inch - it passes my "
              "five-year test and matches how I already buy things.",
}


def set_log_path(path: str | None) -> None:
    global _log_path
    _log_path = str(path) if path else None


def reset_intents() -> None:
    with _lock:
        _intents.clear()


def intents() -> dict[str, int]:
    with _lock:
        return dict(_intents)


def _log(intent: str) -> None:
    with _lock:
        _intents[intent] = _intents.get(intent, 0) + 1
        if _log_path:
            with open(_log_path, "a", encoding="utf-8") as f:
                f.write(f"{intent}\n")


def _content(text: str) -> str:
    if "Return a JSON object with exactly these keys" in text:
        _log("extract")
        return json.dumps(EXTRACT)
    if "write a first-person profile" in text:
        _log("persona")
        return PERSONA
    if "summarizing one community of facts" in text:
        _log("community")
        return COMMUNITY
    if "Reply directly to the question in plain text." in text:
        _log("reason")
        return REASON["answer"]
    if "Return JSON with keys" in text:
        _log("reason")
        return json.dumps(REASON)
    _log("generic")
    return "ok"


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, obj: dict, code: int = 200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"ok": True})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send({"error": "bad json"}, 400)
            return
        messages = req.get("messages") or []
        text = "\n".join(str(m.get("content", "")) for m in messages)
        if req.get("stream"):
            content = _content(text)
            chunks = [{"id": "chatcmpl-mock", "object": "chat.completion.chunk",
                       "created": 0, "model": req.get("model", "mock-gpt"),
                       "choices": [{"index": 0, "delta": {"content": content[i:i+12]},
                                    "finish_reason": None}]}
                      for i in range(0, len(content), 12)]
            body = ("".join("data: " + json.dumps(c) + "\n\n" for c in chunks)
                    + "data: [DONE]\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send({
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": 0,
            "model": req.get("model", "mock-gpt"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": _content(text)},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        })


def start(port: int = 8791) -> ThreadingHTTPServer:
    """Start the mock in a daemon thread; call .shutdown() to stop."""
    reset_intents()
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv