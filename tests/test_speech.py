"""Pocket TTS contract checks without model downloads."""
from io import BytesIO
import wave
from types import SimpleNamespace
import numpy as np
import pytest
from fastapi.testclient import TestClient
from digital_twin.speech import PocketSpeech, SpeechBusy
import digital_twin.server as server


def test_local_wav_cache_and_guards():
    engine = PocketSpeech()
    calls = []
    audio = SimpleNamespace(detach=lambda: SimpleNamespace(cpu=lambda: SimpleNamespace(numpy=lambda: np.array([-2., 0., 2.]))))
    engine.model = SimpleNamespace(sample_rate=24000, get_state_for_audio_prompt=lambda voice: voice,
        generate_audio=lambda state, text: calls.append((state, text)) or audio)
    output = engine.synthesize("A fictional example.")
    with wave.open(BytesIO(output), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 24000)
        assert np.frombuffer(wav.readframes(3), dtype="<i2").tolist() == [-32767, 0, 32767]
    assert engine.synthesize("A fictional example.") == output
    assert len(calls) == 1
    for text, voice in [(" ", "alba"), ("a" * 4001, "alba"), ("hello", "../voice"), ("नमस्ते", "alba")]:
        with pytest.raises(ValueError):
            engine.synthesize(text, voice)
    with engine.lock:
        with pytest.raises(SpeechBusy):
            engine.synthesize("A different reply.")


def test_speech_endpoint_contract(monkeypatch):
    client = TestClient(server.app)
    monkeypatch.setattr(server.speech, "synthesize", lambda text, voice: b"RIFFtest")
    result = client.post("/api/speech", json={"text": "Hello", "voice": "alba"})
    assert result.status_code == 200 and result.headers["content-type"] == "audio/wav"
    assert result.headers["cache-control"] == "no-store"
    assert client.post("/api/speech", json={"text": "Hello", "voice": "untrusted"}).status_code == 422
    assert client.post("/api/speech", json={"text": "a" * 4001}).status_code == 422
    def busy(*args):
        raise SpeechBusy("Please retry")
    monkeypatch.setattr(server.speech, "synthesize", busy)
    result = client.post("/api/speech", json={"text": "Hello"})
    assert result.status_code == 429 and result.headers["retry-after"] == "3"
    def broken(*args):
        raise RuntimeError("private internal detail")
    monkeypatch.setattr(server.speech, "synthesize", broken)
    result = client.post("/api/speech", json={"text": "Hello"})
    assert result.status_code == 503 and "private" not in result.text
