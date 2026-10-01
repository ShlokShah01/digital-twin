# Digital Twin

An AI "digital twin" of a person: it learns your writing style, speaking
patterns, frequently used words, preferences and decision rules from your
journals, notes, chats, emails and CSV data, stores them in a hybrid
vector + knowledge-graph index, and answers "What would I probably choose?"

```
digital-twin demo                                   generate demo data (Alex Carter)
digital-twin build --data data/raw/demo            ingest + graph + profile
digital-twin ask "Should I buy a flagship?" \
    --options "Buy new;Buy refurbished;Wait"        decision question
digital-twin profile                                print the learned profile
digital-twin serve --port 8000                      FastAPI + web UI
```

## How it works

1. **Ingestion** (`pipeline.py`) - reads plain text, Markdown, JSON, CSV,
   chunks (word-based, defaults `chunk_words=150`, `chunk_overlap=30`) and
   embeds each chunk with `BAAI/bge-small-en-v1.5` (FastEmbed, 384 dims).
2. **Extraction** - an LLM (OpenAI-compatible) pulls out name guess,
   preferences, decision patterns, facts, entities and relations from each
   doc. With no API key, a heuristic offline miner
   (`extraction.offline_extract`) does the same from sentence signals
   ("I like / I avoid / would rather", time-horizon rules, project names).
3. **Profile** (`profile.py`) - style statistics (avg sentence length,
   recurring words), merged preferences and decision rules, dominant topics.
4. **Graph + GraphRAG** (`graph.py`, `graphrag.py`) - EntityResolver +
   keyword/LLM keyword IDF build a NetworkX graph; Louvain communities get
   LLM summaries (fallback = centroid keyword list).
5. **Answering** (`engine.py`) - retrieve top chunks + graph local/global
   context, rerank with Laya, build an evidence-first "brief", then decide:
   - **Laya** (`laya_agent.py`) is a calibrated classifier/reranker
     (cross-platform `laya` package, `convaiinnovations/laya`). Two signals
     are forward-passed together and **ensembled** into one probability
     distribution: per-option `noul` answers (P(true), normalized) and a
     multi-label `choice` question. The checkpoint ships invalid
     temperatures (`RuntimeWarning`, cosmetic) and - per Laya's own model
     card - base checkpoints are not reliable zero-shot decision engines, so
     Laya is treated as a System-1 cross-check, never the sole judge.
   - **LLM** (when an `OPENAI_API_KEY` is set) is the grounded narrator: it
     reasons in the twin's first-person voice over the same brief. Agreement
     between LLM and Laya raises confidence; disagreement lowers it and is
     noted in the reasoning.

> **Apple Silicon note:** the Apple-only `laya-mlx` backend is not required.
> This project uses the cross-platform `laya` package on CPU
> (`device="cpu"`), which works on Windows/Linux/macOS.

## Setup

```
python -m venv .venv
.venv\Scripts\Activate.ps1            # Windows
pip install -e .
pip install -e ".[dev]"               # optional, for the test suite
```

Copy `.env.example` to `.env` and add an LLM key (optional - without one the
pipeline runs fully offline with the heuristic miner and Laya).

NVIDIA NIM is the recommended LLM provider. Get up to two `nvapi-...` keys from
https://build.nvidia.com, point the OpenAI-compatible client at NVIDIA and pick
a hosted model:

```
OPENAI_API_KEY=nvapi-xxxx                 # key 1 (required for LLM mode)
OPENAI_API_KEY_2=nvapi-yyyy               # key 2 (optional, second rate slot)
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
DIGITAL_TWIN_LLM_MODEL=openai/gpt-oss-20b   # primary narrator/decider model
DIGITAL_TWIN_LLM_FALLBACK_MODEL=                        # optional; alternate-key retry is enabled
DIGITAL_TWIN_LLM_CONTEXT=131072   # input token budget (long docs/briefs are front-loaded to fit)
DIGITAL_TWIN_LLM_TIMEOUT=45    # total retry deadline
DIGITAL_TWIN_LLM_RPM=40        # strict rolling-minute cap per key
```

With both keys set, requests are round-robined across them (each capped at
`DIGITAL_TWIN_LLM_RPM` requests/minute, roughly doubling effective throughput)
and transient failures (429, 5xx, network blips, empty responses) are retried
with exponential backoff while rotating keys, so a busy/free-tier NIM model
recovers instead of falling back. If the primary model is retired or keeps
failing, `DIGITAL_TWIN_LLM_FALLBACK_MODEL` is tried once per key. Hard errors
(bad key) fail immediately to the offline path. The same client powers the
chatbot answers **and** the `build` pipeline (extraction, persona, community
summaries); without any key both degrade to the offline heuristic path. Any
OpenAI-compatible endpoint (Ollama, vLLM, LM Studio, OpenAI itself) also works
by changing `OPENAI_BASE_URL` and `DIGITAL_TWIN_LLM_MODEL`.

## Commands (Windows PowerShell)

```
digital-twin demo                                   generate demo data (Alex Carter)
digital-twin build --data data/raw/demo            ingest + graph + profile (offline)
digital-twin ask "New laptop?" --options "A;B;C"   decision question
digital-twin profile                                print the learned profile
digital-twin serve --port 8000                      FastAPI + web UI
```

Everything above runs fully offline (no `OPENAI_API_KEY` needed). The web
server writes its PID and log to `data/twin/server.pid` and
`data/twin/server.log`; stop it with:

```
Stop-Process -Id (Get-Content data/twin/server.pid)
```

Restart after an edit:

```
$cmd = "digital-twin serve --port 8000"; $s = New-Object -ComObject WScript.Shell
$s.Run($cmd, 0, $False)
```

The React frontend is pre-built into `web/dist` and served by FastAPI at
`http://127.0.0.1:8000/`. To develop on the UI, run the Vite dev server
(live-reloads against the same API, CORS is enabled for it only):

```
cd web
npm install          # once
npm run dev          # http://localhost:5173
npm run build        # rebuild web/dist (the app FastAPI serves)
```

## Testing

```
pip install -e ".[dev]"
pytest
```

57 tests cover text utilities, offline mining, chunking, style analysis,
the vector store, graph/GraphRAG, the offline build pipeline, incremental
ingest, engine ask paths - including a stubbed-Laya + stub-LLM pass over the
agreement/conflict/LLM-degraded branches - and a full HTTP contract suite
(`tests/test_server.py`) that exercises `/api/health`, `/api/profile`,
`/api/graph`, `/api/build`, `/api/ingest`, `/api/ask` and the LLM path
through the live server against a local mock OpenAI-compatible server
(`tests/mocks/mock_llm.py`) **without needing a real API key**. Set
`DIGITAL_TWIN_NO_LAYA=1` or `laya_enabled=False` to skip Laya entirely in
tests and CI.

## Why the two Laya signals?

- `noul` ("true/false", P(true) per option) is calibrated but near-flat on
  novel scenarios (e.g. 0.72/0.68/0.62 for a three-way laptop choice).
- Multi-label `choice` logits spread better (e.g. refurbished 0.44 top) but
  are not individually calibrated.
- Averaging the normalized distributions gives a sturdier ranking than
  either alone; the raw values of both are kept in `answer.meta.laya`
  (`noul_raw`, `choice_probs`, `ensemble`) for inspection.

## API

- `GET  /` - web app (React, built from `web/dist`)
- `GET  /api/health` - status (`twin_built`, `chunks`, `llm`)
- `GET  /api/profile` - profile summary (persona, style, preferences,
  decision patterns, stats)
- `GET  /api/graph` - knowledge graph communities for the viz view
- `POST /api/build` - `{"data": "dir", "no_llm": false}`
- `POST /api/ingest` - `{"path": "..."}`
- `POST /api/ask` - `{"question": "...", "options": ["A", "B"]}`

Every `ask` response reports its reasoning basis honestly in `answer.meta`:
`resolution` (`agreement` | `conflict` | `llm_only` | `laya_only` | `none`),
`llm_used`, `llm_enabled`, `laya_used` and the raw Laya signals at
`answer.meta.laya` (`noul_raw`, `choice_probs`, `ensemble`). On a conflict
the LLM's reasoned pick prevails and confidence is set to `0.6 * llm_conf`;
the caution is surfaced in the UI.

## Notes

- **PowerShell gotcha:** semicolons split commands. Pass options as one
  quoted string: `--options "A;B;C"`. Fewer than 2 options disables the
  Laya vote (a single option is trivially P(true)=1).
- Laya/model weights are cached in `~/.cache/huggingface` (set
  `HF_HUB_DISABLE_SYMLINKS_WARNING=1` to silence the symlink warning).
- On low-memory machines Laya (torch) can fail to allocate (Windows
  `os error 1455`). This is caught: the twin degrades gracefully - Laya
  choice/rerank is skipped, the LLM (or template) judges instead.
- Config read from `Config`/env, see `digital_twin/config.py` and
  `.env.example`.

## Response latency

Laya weights are shared across requests and warmed when the server starts, so each chat avoids downloading/checking and loading a fresh checkpoint. On this Windows machine the project `.env` selects `DIGITAL_TWIN_LAYA_DEVICE=cuda`; `GET /api/health` reports the actual warmed device and `laya_loaded`.

The narrator is NVIDIA-hosted `openai/gpt-oss-20b` with low reasoning effort. It passed both fictional English/Hindi checks in 3.2–5.2 seconds; Lightning timed out in the same comparison. After removing the JSON decision report from ordinary chat, the exact chat-generation path returned valid answers in 1.89 and 1.77 seconds through the two keys with a longer fictional brief. These are synthetic hosted-API measurements, not a guaranteed end-to-end response time. Sanitized results are in `data/twin/model_benchmark.json`. Streaming requests retry the other key without backoff; every HTTP call, including failed and format-retry calls, counts toward that key’s strict rolling-minute limit.

`DIGITAL_TWIN_LLM_TIMEOUT=20` bounds the retry budget and `DIGITAL_TWIN_LLM_ATTEMPT_TIMEOUT=8` limits provider requests. Ordinary chat streams plain answer text, without generating a JSON decision report; structured choice questions keep their existing report. Greetings and identity questions answer locally. Provider failures produce a retryable error rather than a false missing-key answer. Retired models go directly to failover; authentication failures fail immediately; empty answers are never treated as successful. Provider response times still vary.

Check GPU scoring/reranking with `.venv\Scripts\python.exe -B tests\check_laya_gpu.py`. Latency regressions are in `tests/test_latency.py`; the full API/engine tests continue to cover bot behavior. Chat displays only the answer; timing remains available in API metadata. The UI uses the same hash routes and existing localStorage chat history.

### Conversation tools

Search saved conversations by title, question, or answer in the sidebar. Use **Export chat** to download the current conversation as Markdown. History is local to this browser and device; export important chats before clearing browser storage. Open **Your profile → Resources** for usage guides, troubleshooting, and official documentation.
