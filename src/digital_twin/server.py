"""FastAPI assistant for the digital twin.

Routes:
  GET  /               -> web app (dashboard / ask / profile / graph / how-it-works)
  GET  /api/health     -> status
  GET  /api/profile    -> built profile (summary)
  GET  /api/graph      -> knowledge graph + community clusters (for viz)
  POST /api/build      -> run the build pipeline (synchronous)
  POST /api/ingest     -> {path} add one file incrementally
  POST /api/ask        -> {question, options?} twin answer
"""

from __future__ import annotations

import logging
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal
from .speech import speech, SpeechBusy
from starlette.concurrency import run_in_threadpool

from .config import ROOT, load_config
from .llm import LLMUnavailable

log = logging.getLogger(__name__)

_cfg = load_config()
_runtime_laya = None


@asynccontextmanager
async def lifespan(app):
    global _runtime_laya
    if _cfg.laya_enabled:
        from .laya_agent import LayaEngine
        _runtime_laya = LayaEngine(checkpoint=_cfg.laya_checkpoint, device=_cfg.laya_device)
        await run_in_threadpool(_runtime_laya._load)
    # Warm embeddings before accepting chats, just as we warm the CUDA model.
    from .embedder import Embedder
    await run_in_threadpool(Embedder(_cfg.embed_model).dim)
    try:
        await run_in_threadpool(speech.warmup)
    except Exception:
        log.exception("Pocket TTS could not warm up; chat remains available")
    yield


app = FastAPI(title="Digital Twin", version="0.1.0", lifespan=lifespan)

# Local frontend development only; production is same-origin (served by this app).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_web = Path(ROOT) / "web"
_dist = _web / "dist"
if _dist.exists():
    _assets = _dist / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=20000)
    options: list[str] = Field(default_factory=list)


class IngestRequest(BaseModel):
    path: str


class BuildRequest(BaseModel):
    data: str | None = None
    no_llm: bool = False


def _twin():
    from .engine import Twin
    return Twin(_cfg)


def _profile_summary():
    from .profile import load_profile
    prof = load_profile(_cfg.profile_path)
    if prof is None:
        return None
    return {
        "name": prof.name,
        "persona": prof.persona,
        "built_at": prof.built_at,
        "stats": prof.stats,
        "topics": prof.topics[:10],
        "preferences": [p.model_dump() for p in prof.preferences[:10]],
        "decision_patterns": [p.model_dump() for p in prof.decision_patterns[:8]],
        "style": prof.style.model_dump(),
    }


@app.get("/")
def index():
    # prefer the built React app (web/dist); fall back to the dev entry
    for p in (_dist / "index.html", _web / "index.html"):
        if p.exists():
            return FileResponse(p)
    return {"status": "no web app found - use the API"}


@app.get("/api/health")
def health():
    from .vector_store import VectorStore
    from .profile import load_profile
    from .embedder import Embedder
    store = VectorStore(_cfg.lancedb_path, dim=Embedder(_cfg.embed_model).dim())
    prof = load_profile(_cfg.profile_path)
    return {
        "ok": True,
        "speech": {"model": "pocket-tts", "device": "cpu", "loaded": speech.model is not None},
        "llm": bool(_cfg.llm_api_key) and _cfg.llm_enabled,
        "chunks": store.count(),
        "laya_enabled": _cfg.laya_enabled,
        "laya_device": str(_runtime_laya._agent.device) if _runtime_laya and _runtime_laya._agent else _cfg.laya_device,
        "laya_loaded": bool(_runtime_laya and _runtime_laya._agent),
        "llm_model": _cfg.llm_model if _cfg.llm_enabled else None,
        "twin_built": prof is not None,
        "raw_dir": str(_cfg.raw_dir),
    }


@app.get("/api/profile")
def profile_endpoint():
    summary = _profile_summary()
    if summary is None:
        raise HTTPException(404, "No twin built yet. POST /api/build first.")
    return summary


@app.get("/api/graph")
def graph_endpoint():
    """Knowledge graph + community clusters for the visualization view."""
    from .graph import load_graph, community_labels

    graph = load_graph(_cfg.graph_path)
    if not graph.nodes:
        return {
            "built": False,
            "stats": {"nodes": 0, "edges": 0, "communities": 0, "facts": 0, "entities": 0},
            "clusters": [], "comm_links": [], "nodes": [], "links": [],
        }
    node_by_id = {n.id: n for n in graph.nodes}
    labels = community_labels(graph)
    clusters = [
        {"id": cid, "label": labels.get(cid, [])[:5], "size": len(members),
         "members": [node_by_id[m].label for m in members[:6] if m in node_by_id]}
        for cid, members in sorted(graph.communities.items(), key=lambda kv: -len(kv[1]))
    ]
    node_comm = {node_id: cid for cid, members in graph.communities.items() for node_id in members}
    ordered = sorted(graph.communities, key=lambda c: -len(graph.communities[c]))
    comm_index = {cid: i for i, cid in enumerate(ordered)}
    agg: dict[tuple[str, str], int] = {}
    for e in graph.edges:
        ca, cb = node_comm.get(e.src), node_comm.get(e.tgt)
        if ca is None or cb is None or ca == cb:
            continue
        key = tuple(sorted((comm_index[ca], comm_index[cb])))
        agg[key] = agg.get(key, 0) + 1
    comm_links = [
        {"source": ca, "target": cb, "weight": w}
        for (ca, cb), w in sorted(agg.items(), key=lambda kv: -kv[1])[:80]
    ]
    top_edges = sorted(graph.edges, key=lambda e: e.weight, reverse=True)[:240]
    links = [
        {"source": node_by_id[e.src].label if e.src in node_by_id else e.src,
         "target": node_by_id[e.tgt].label if e.tgt in node_by_id else e.tgt,
         "kind": e.kind}
        for e in top_edges
    ]
    order = {"entity": 0, "keyword": 1, "chunk": 2}
    nodes = [
        {"id": n.id, "label": n.label, "kind": n.kind,
         "community": str(comm_index.get(node_comm.get(n.id, ""), 0))}
        for n in sorted(graph.nodes, key=lambda n: (order.get(n.kind, 3), n.label))
    ]
    return {
        "built": True,
        "stats": {
            "nodes": len(graph.nodes), "edges": len(graph.edges),
            "communities": len(graph.communities),
            "facts": sum(1 for n in graph.nodes if n.kind == "keyword"),
            "entities": sum(1 for n in graph.nodes if n.kind == "entity"),
        },
        "clusters": clusters, "comm_links": comm_links,
        "nodes": nodes, "links": links,
    }


@app.post("/api/build")
def build_endpoint(req: BuildRequest):
    from .pipeline import build
    if req.data:
        src = Path(req.data)
        if not src.is_dir():
            raise HTTPException(400, f"data path is not a directory: {req.data}")
    try:
        res = build(_cfg, raw_dir=req.data, use_llm=False if req.no_llm else True)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, str(e))
    return {
        "documents": res.n_documents,
        "chunks": res.n_chunks,
        "facts": res.n_facts,
        "entities": res.n_entities,
        "graph": {"nodes": res.n_nodes, "edges": res.n_edges, "communities": res.n_communities},
        "llm": res.llm_used,
    }


@app.post("/api/ingest")
def ingest_endpoint(req: IngestRequest):
    from .pipeline import add_source
    src = Path(req.path)
    if not src.is_file():
        raise HTTPException(400, f"not a readable file: {req.path}")
    try:
        out = add_source(_cfg, req.path)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, str(e))
    return out


@app.post("/api/ask")
def ask_endpoint(req: AskRequest):
    twin = _twin()
    try:
        ans = twin.ask(req.question, options=req.options)
    except LLMUnavailable as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return ans.model_dump()

@app.post("/api/ask/stream")
async def ask_stream_endpoint(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(400, "empty question")
    loop = asyncio.get_running_loop()
    events = asyncio.Queue()

    def publish(kind, data):
        loop.call_soon_threadsafe(events.put_nowait, {"type": kind, "data": data})

    def work():
        try:
            ans = _twin().ask(req.question, options=req.options,
                               on_text=lambda text: publish("text", text))
            publish("answer", ans.model_dump())
        except Exception as exc:
            log.exception("Streaming answer failed")
            publish("error", str(exc))

    async def stream():
        worker = asyncio.create_task(run_in_threadpool(work))
        try:
            yield json.dumps({"type": "status", "data": "Preparing evidence"}) + "\n"
            while True:
                event = await events.get()
                yield json.dumps(event, ensure_ascii=False) + "\n"
                if event["type"] in ("answer", "error"):
                    break
        finally:
            # Keep the worker alive until its bounded provider request finishes.
            # Retrieval/LLM work runs off the event loop so health stays responsive.
            if not worker.done():
                worker.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: Literal["alba", "marius", "anna"] = "alba"


@app.post("/api/speech")
def speech_endpoint(req: SpeechRequest):
    try:
        audio = speech.synthesize(req.text, req.voice)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except SpeechBusy as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "3"}) from exc
    except Exception as exc:
        log.exception("Pocket TTS synthesis failed")
        raise HTTPException(503, "Speech is unavailable. Please try again shortly.") from exc
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
