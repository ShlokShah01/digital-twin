"""Run with .venv/Scripts/python.exe -B tests/check_laya_gpu.py."""
import torch

from digital_twin.config import load_config
from digital_twin.laya_agent import LayaEngine

cfg = load_config()
assert cfg.laya_enabled, "Laya is disabled"
assert torch.device(cfg.laya_device).type == "cuda", cfg.laya_device
assert torch.cuda.is_available(), "Install CUDA-enabled PyTorch"
engine = LayaEngine(checkpoint=cfg.laya_checkpoint, device=cfg.laya_device)
agent = engine._load()
assert agent is not None, engine._load_error
assert agent.device.type == "cuda", f"Laya fell back to {agent.device}"
assert all(p.device.type == "cuda" for p in agent.model.parameters())
assert all(b.device.type == "cuda" for b in agent.model.buffers())
assert engine.predict_choice(
    "I prefer saving money and buying refurbished devices with a warranty.",
    ["Buy a new flagship", "Buy refurbished with a warranty"],
) is not None, "GPU decision inference failed"
assert engine.rerank(
    "Which laptop would I buy?",
    ["I buy refurbished laptops with warranties.", "I enjoy walking."],
) is not None, "GPU reranking failed"
torch.cuda.synchronize()
print(f"PASS: Laya decision scoring and reranking on {torch.cuda.get_device_name(0)}")
print(f"Model device: {agent.device}; CUDA allocated: {torch.cuda.memory_allocated() / 2**20:.0f} MiB")