"""Command-line interface:

    digital-twin demo                generate the demo dataset (Alex Carter)
    digital-twin build [--data DIR]  build the profile / ingest + graph + profile
    digital-twin ask "Q" --options "A;B;C"  ask the twin a decision question
    digital-twin profile             print the learned profile
    digital-twin serve --port 8000   run the FastAPI assistant

NOTE (PowerShell): separate options with ';' INSIDE one quoted argument,
e.g.  digital-twin ask "..." --options "A;B;C"
Semicolons between separate quoted strings are PowerShell statement
separators, not arguments. Give at least two options for a Laya vote.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from .config import load_config

log = logging.getLogger(__name__)


def _split_options(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [o.strip() for o in re.split(r"[;|]", raw) if o.strip()]


def cmd_demo(args) -> int:
    from .demo import generate
    dest = Path(args.dir)
    files = generate(dest)
    print(f"Demo dataset written to {dest}:")
    for f in files:
        print(f"  {f}")
    print("\nNow run:  digital-twin build --data " + str(dest))
    return 0


def cmd_build(args) -> int:
    from .pipeline import build
    cfg = load_config()
    res = build(cfg, raw_dir=args.data, use_llm=False if args.no_llm else True)
    print("Twin built:")
    print(f"  documents : {res.n_documents}")
    print(f"  chunks    : {res.n_chunks}")
    print(f"  style     : {'computed' if res.style_ok else 'failed'}")
    print(f"  facts     : {res.n_facts}")
    print(f"  entities  : {res.n_entities}")
    print(f"  graph     : {res.n_nodes} nodes / {res.n_edges} edges / {res.n_communities} communities")
    print(f"  LLM       : {'used' if res.llm_used else 'not used (no LLM key or --no-llm)'}")
    print(f"\nAsk it something:  digital-twin ask \"What would I choose, laptop or...?\"")
    return 0


def cmd_ask(args) -> int:
    from .engine import Twin
    cfg = load_config()
    try:
        twin = Twin(cfg)
        ans = twin.ask(args.question, options=_split_options(args.options))
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(ans.model_dump_json(indent=2))
        return 0
    print(f"Q: {ans.question}")
    if ans.choices:
        print("\nLaya calibrated probabilities:")
        for c in ans.choices:
            bar = "#" * int(c.probability * 20)
            print(f"  {c.rank:>2}. {c.probability*100:5.1f}%  {c.option[:72]}  [{bar}]")
        print(f"\nPredicted choice: {ans.choice}")
    print(f"Confidence: {ans.confidence:.3f}")
    print(f"\n{ans.answer}")
    if ans.reasoning:
        print(f"\nReasoning: {ans.reasoning}")
    if ans.sources:
        print("\nSources:")
        for s in ans.sources[:5]:
            print(f"  - [{s.source}] {s.snippet[:90]}...")
    return 0


def cmd_profile(args) -> int:
    from .profile import load_profile
    cfg = load_config()
    prof = load_profile(cfg.profile_path)
    if prof is None:
        print(f"no profile found ({cfg.profile_path}). Run `digital-twin build` first.")
        return 2
    if args.json:
        print(prof.model_dump_json(indent=2))
        return 0
    print(f"Digital twin of: {prof.name}")
    print(f"built at: {prof.built_at}")
    print(f"\nPersona:\n{prof.persona}\n")
    if prof.preferences:
        print("Preferences:")
        for p in prof.preferences[:12]:
            print(f"  [{p.stance}] {p.domain}: {p.statement[:110]}")
    if prof.decision_patterns:
        print("\nDecision patterns:")
        for p in prof.decision_patterns[:10]:
            print(f"  - {p.name}: {p.behavior[:100]}")
    print(f"\nStyle: formality={prof.style.formality}, avg sentence={prof.style.mean_sentence_len} words, "
          f"vocab={prof.style.vocabulary}, TTR={prof.style.ttr}, sentiment={prof.style.sentiment_mean}")
    print(f"top words: {', '.join(w for w, _ in prof.style.top_words[:10])}")
    print(f"stats: {json.dumps(prof.stats)}")
    return 0


def cmd_serve(args) -> int:
    from .server import app
    import uvicorn
    cfg = load_config()
    cfg.twin_dir.mkdir(parents=True, exist_ok=True)
    pid_path = cfg.twin_dir / "server.pid"
    log_path = cfg.twin_dir / "server.log"
    pid_path.write_text(str(__import__("os").getpid()), encoding="utf-8")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(fh)
    print(f"Twin server on http://{args.host}:{args.port}  (data: {cfg.twin_dir})")
    print(f"pid file: {pid_path}   log: {log_path}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="digital-twin", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    pd = sub.add_parser("demo", help="generate the demo dataset")
    pd.add_argument("--dir", default=str(Path("data/raw/demo")))
    pd.set_defaults(func=cmd_demo)

    pb = sub.add_parser("build", help="ingest + embed + graph + profile")
    pb.add_argument("--data", default=None, help="source directory (default $DIGITAL_TWIN_RAW_DIR or data/raw)")
    pb.add_argument("--no-llm", action="store_true", help="skip LLM extraction/persona (offline mode)")
    pb.set_defaults(func=cmd_build)

    pa = sub.add_parser("ask", help='ask the twin - e.g. ask "Q" --options "A;B;C"')
    pa.add_argument("question")
    pa.add_argument("--options", default=None,
                    help="semicolon-separated options in ONE quoted string: \"A;B;C\" (>=2 for a decision vote)")
    pa.add_argument("--json", action="store_true")
    pa.set_defaults(func=cmd_ask)

    pp = sub.add_parser("profile", help="show the learned profile")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_profile)

    ps = sub.add_parser("serve", help="run the FastAPI assistant + web UI")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--port", type=int, default=8000)
    ps.set_defaults(func=cmd_serve)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())