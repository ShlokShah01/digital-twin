"""Local, CPU-only Pocket TTS with cached weights and voice conditioning."""
from functools import lru_cache
from io import BytesIO
import re
import threading
import wave
import numpy as np

VOICES = ("alba", "marius", "anna")

class SpeechBusy(Exception):
    pass

class PocketSpeech:
    def __init__(self):
        self.model = None
        self.voices = {}
        self.lock = threading.Lock()

    def _load(self):
        if self.model is None:
            import torch
            from pocket_tts import TTSModel
            torch.set_num_threads(4)
            self.model = TTSModel.load_model(language="english", temp=0.3,
                sampler_decode_steps=1, noise_clamp=None, eos_threshold=-4.0, quantize=True).to("cpu")
        return self.model

    def warmup(self):
        with self.lock:
            model = self._load()
            self.voices["alba"] = model.get_state_for_audio_prompt("alba")

    @lru_cache(maxsize=8)
    def synthesize(self, text: str, voice: str = "alba") -> bytes:
        text = text.strip()
        if not text or len(text) > 4000:
            raise ValueError("Speech requires between 1 and 4000 characters.")
        if voice not in VOICES:
            raise ValueError("Unsupported voice.")
        if re.search(r"[\u0900-\u097f]", text):
            raise ValueError("This Pocket TTS voice supports English replies. Hindi speech needs a separate language model.")
        # ponytail: one CPU generation at a time; a worker pool only if concurrent listening is needed.
        if not self.lock.acquire(blocking=False):
            raise SpeechBusy("Another reply is being voiced. Please try again shortly.")
        try:
            model = self._load()
            if voice not in self.voices:
                self.voices[voice] = model.get_state_for_audio_prompt(voice)
            audio = model.generate_audio(self.voices[voice], text).detach().cpu().numpy()
            if not np.isfinite(audio).all() or not audio.size:
                raise RuntimeError("The speech model returned invalid audio.")
            pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
            output = BytesIO()
            with wave.open(output, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(model.sample_rate)
                wav.writeframes(pcm.tobytes())
            return output.getvalue()
        finally:
            self.lock.release()

speech = PocketSpeech()
