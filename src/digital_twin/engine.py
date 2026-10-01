"""The digital-twin query engine: given a question (and optional options),
retrieve evidence, rerank with Laya, pull graph/community context, then answer
"What would this person probably choose/do/say?".

Decisions: Laya's two calibrated signals (per-option noul P(true) + multi-label
choice logits) are ensembled into a probability distribution, and - when an LLM
is available - the LLM is the primary narrator/decider grounded in the same
evidence, with Laya kept as a cross-check in the UI. That architecture is
deliberate: Laya's model card is honest that its base checkpoints are not
reliable zero-shot decision engines, so relying on it alone would produce
confidently-wrong guesses on novel questions."""

from __future__ import annotations

import json
import logging
from typing import Sequence
from time import perf_counter

from .config import Config
from .embedder import Embedder
from .graph import keyword_idf_from_chunks
from .graphrag import GraphRAG
from .laya_agent import LayaEngine
from .llm import ChatClient, LLMUnavailable
from .models import Answer, ChoiceOutcome, Profile, SourceHit
from .profile import load_profile
from .text_utils import text_terms, tokens
from .vector_store import VectorStore

log = logging.getLogger(__name__)


class Twin:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.embedder = Embedder(cfg.embed_model)
        self.store = VectorStore(cfg.lancedb_path, dim=self.embedder.dim())
        self.laya = LayaEngine(checkpoint=cfg.laya_checkpoint, device=cfg.laya_device,
                           enabled=cfg.laya_enabled)
        self.llm = ChatClient(cfg)
        self.profile: Profile | None = None
        self.graphrag: GraphRAG | None = None
        self.idf_map: dict[str, float] = {}

    # -------------------------------------------------------------------------
    def load(self) -> bool:
        """Load built artifacts; False when nothing is built yet."""
        self.profile = load_profile(self.cfg.profile_path)
        chunks = self._load_chunk_index()
        self.graphrag = GraphRAG.load(self.embedder, self.cfg.graph_path,
                                      self.cfg.community_path, chunks)
        self.idf_map = keyword_idf_from_chunks(list(chunks.values()))
        return self.profile is not None and self.store.count() > 0

    def ensure_built(self) -> None:
        if not self.load():
            raise RuntimeError(
                "No digital twin built yet. Run `digital-twin build` first, "
                "or POST /api/build.")

    def _load_chunk_index(self) -> dict:
        from .models import Chunk
        import json as _json
        p = self.cfg.index_path
        if not p.exists():
            return {}
        try:
            raw = _json.loads(p.read_text(encoding="utf-8"))
            return {c["id"]: Chunk(**c) for c in raw}
        except Exception:  # noqa: BLE001
            return {}

    # -------------------------------------------------------------------------
    def ask(self, question: str, options: Sequence[str] | None = None, *, on_text=None) -> Answer:
        started = perf_counter()
        # Greetings don't need private evidence or a remote model request.
        if not options and question.strip().casefold().strip("!?. ") in {"hi", "hello", "hey", "hlo"}:
            return Answer(question=question.strip(), answer="Hi! How can I help?",
                          model="greeting", meta={"llm_used": False, "laya_used": False})
        if not options and question.strip().casefold().strip("!?. ") in {
                "who are you", "what are you", "what is a digital twin"}:
            return Answer(question=question.strip(),
                          answer="I'm your digital twin, an AI assistant that uses your saved knowledge to help answer questions and explore decisions.",
                          model="identity", meta={"llm_used": False, "laya_used": False})
        self.llm.on_text = on_text
        self.ensure_built()
        assert self.profile is not None and self.graphrag is not None

        options = [str(o).strip() for o in (options or [])]
        options = [o for o in options if o]
        qw = (question or "").strip()
        if not qw:
            raise ValueError("empty question")

        query_terms = text_terms(qw)
        qvec = self.embedder.embed_one(qw)

        # 1. retrieve + rerank ----------------------------------------------
        hits = self.store.hybrid_search(qvec, query_terms, self.idf_map,
                                        limit=self.cfg.retrieve_k)
        texts = [h["text"] for h in hits]
        order = self.laya.rerank(qw, texts, top_k=self.cfg.rerank_k) if texts else None
        if order is not None:
            hits = [hits[i] for i in order][: self.cfg.rerank_k]
        else:
            hits = hits[: self.cfg.rerank_k]

        sources = [
            SourceHit(chunk_id=h["chunk_id"], source=h["source"],
                      snippet=h["text"][:500], score=round(float(h["score"]), 4))
            for h in hits
        ]

        # 2. graph/community context ----------------------------------------
        local_ctx = self.graphrag.local_search(qw, query_terms, qvec, k=self.cfg.graph_k)
        global_ctx = self.graphrag.global_search(qvec, query_terms, k=self.cfg.community_k)
        graph_context = bool(local_ctx or global_ctx)

        # 3. build the decision brief ---------------------------------------
        brief = self._brief(question=qw, options=options, sources=hits,
                            local_ctx=local_ctx, global_ctx=global_ctx)

        # 4a. Laya System-1 signals + ensemble -----------------------------------
        probabilities: dict[str, float] = {}
        choice: str | None = None
        confidence = 0.0
        laya_meta: dict = {}
        if options:
            pred = self.laya.predict_choice(brief, options)
            if pred:
                probs_noul = pred["probabilities"]
                probs_choice = pred.get("choice_probs") or {}
                # ensemble: mean of the two calibrated distributions
                if probs_choice:
                    probabilities = {
                        opt: 0.5 * probs_noul.get(opt, 0.0) + 0.5 * probs_choice.get(opt, 0.0)
                        for opt in options
                    }
                else:
                    probabilities = dict(probs_noul)
                choice = max(probabilities, key=probabilities.get)
                confidence = probabilities[choice]
                laya_meta = {
                    "noul_raw": {k: round(v, 4) for k, v in pred["noul"].items()},
                    "choice_probs": {k: round(v, 4) for k, v in probs_choice.items()},
                    "ensemble": {k: round(v, 4) for k, v in probabilities.items()},
                    "checkpoint": self.cfg.laya_checkpoint,
                }

        # 4b. LLM reasoning in the twin's voice ------------------------------
        prepared = perf_counter()
        answer_text, reasoning, llm_best, llm_conf, used_llm = self._reason(
            question=qw, options=options, brief=brief, local_context=local_ctx)

        # 4c. final choice: LLM is the grounded narrator when present, Laya a
        # calibrated cross-check. Agreement raises confidence, conflict lowers it.
        laya_top = choice
        laya_conf = confidence
        if llm_best is not None:
            if laya_top is None or llm_best == laya_top:
                choice = llm_best
                resolution = "agreement" if laya_top == llm_best else "llm_only"
                confidence = 0.6 * llm_conf + (0.4 * laya_conf if laya_top is not None else 0.0)
                if laya_top is not None and laya_top == llm_best and laya_conf < 0.4:
                    # Laya signals were ambiguous even though the LLM was clear
                    reasoning += ("\n\n(Note: my calibrated Laya signals were fairly "
                                  "flat here - treat the reasoning above as the primary basis.)")
            else:
                choice = llm_best
                confidence = 0.6 * llm_conf
                resolution = "conflict"
                reasoning += ("\n\n(Note: my instant Laya signals leaned toward "
                              f"{laya_top!r}, but the reasoned answer points to {llm_best!r}; "
                              "I am trusting the reasoned read over the instant guess, so "
                              "treat this as lower-confidence.)")
        else:
            choice = laya_top
            confidence = laya_conf
            resolution = "laya_only" if laya_top is not None else "none"

        # no-LLM mode: make the plain-text answer carry the Laya prediction
        if not used_llm and probabilities and choice:
            top_pct = probabilities[choice] * 100
            answer_text = (
                f"My strongest signal points to: {choice} (Laya calibrated "
                f"probability ~{top_pct:.0f}%, ensemble of two decision heads). "
                "Provide your own reasoning with `--options` and an LLM key "
                "to get a first-person explanation.")

        # format probabilities deterministically
        choices_out = [
            ChoiceOutcome(option=opt, probability=round(probabilities.get(opt, 0.0), 4), rank=i + 1)
            for i, opt in enumerate(options)
        ]
        choices_out.sort(key=lambda c: c.probability, reverse=True)
        for i, co in enumerate(choices_out):
            co.rank = i + 1

        return Answer(
            question=qw,
            choice=choice,
            choices=choices_out,
            confidence=round(confidence, 4),
            answer=answer_text,
            reasoning=reasoning,
            sources=sources[:5],
            graph_context=graph_context,
            model=(getattr(self.llm, "last_model", None) or self.cfg.llm_model) if used_llm else "template",
            meta={
                "timing_ms": {"preparation": round((prepared - started) * 1000),
                              "generation": round((perf_counter() - prepared) * 1000)},
                "vector_k": self.cfg.retrieve_k,
                "laya_used": self.laya.available,
                "llm_used": used_llm,
                "llm_enabled": self.llm.enabled,
                "resolution": resolution,
                "n_evidence": len(sources),
                "laya": laya_meta,
                "twin": {
                    "persona": (self.profile.persona or "")[:400],
                    "stats": self.profile.stats,
                    "graph": self.graphrag.stats(),
                },
            },
        )

    # -------------------------------------------------------------------------
    def _brief(self, question, options, sources, local_ctx, global_ctx) -> str:
        """Compact, evidence-first decision brief that fits inside Laya's
        context window. Order matters: the highest-signal content goes first so
        any truncation only drops optional graph prose, never the persona or
        the retrieved evidence. (Options also travel inside each noul question,
        so they are re-stated here for the LLM path but are never load-bearing.)"""
        p = self.profile
        parts = [p.persona[:1200]]

        style = p.style
        decisive = style.decisiveness_tokens
        strong = ", ".join(k for k, _ in sorted(decisive.items(), key=lambda kv: kv[1], reverse=True)[:4])
        parts.append(
            f"Style signals: formality={style.formality}, avg sentence={style.mean_sentence_len} words, "
            f"decisive vocabulary ({strong}) used {sum(decisive.values())} times, "
            f"hedging words used {sum(style.hedges.values())} times, "
            f"sentiment bias={style.sentiment_mean}."
        )
        if p.preferences:
            pref_lines = []
            for pr in p.preferences[:7]:
                pref_lines.append(f"- [{pr.stance}] {pr.statement[:160]}")
            parts.append("Stated preferences:\n" + "\n".join(pref_lines))
        if p.decision_patterns:
            pat_lines = []
            for pat in p.decision_patterns[:5]:
                pat_lines.append(f"- {pat.name}: {pat.behavior[:140]}")
            parts.append("Stated decision rules:\n" + "\n".join(pat_lines))

        # Retrieved evidence goes before the (optional) graph prose.
        if sources:
            ev_lines = []
            for h in sources[:6]:
                ev_lines.append(f"- {h['text'][:220]}")
            parts.append("Most relevant original fragments:\n" + "\n".join(ev_lines))
        if local_ctx:
            parts.append(local_ctx[:1600])
        if global_ctx:
            parts.append(global_ctx[:1400])
        if options:
            parts.append("Candidate options:\n" + "\n".join(f"- {o}" for o in options))
        body = "\n\n".join(parts)
        return f"Question: {question}\n\n{body}"

    # -------------------------------------------------------------------------
    def _reason(self, question, options, brief, local_context) -> tuple[str, str, str | None, float, bool]:
        if not self.llm.enabled:
            return *self._template_answer(question, options, brief), False
        if not options:
            # Stream the answer itself; chat doesn't need a hidden decision report.
            preview = self.llm.on_text
            self.llm.on_text = (
                (lambda text: preview(json.dumps({"answer": text}, ensure_ascii=False)))
                if preview is not None else lambda text: None
            )
            try:
                answer = self.llm.complete_text(
                    brief + "\n\nReply directly to the question in plain text.",
                    system=("You are a digital twin. Answer the question directly in the question's language. "
                            "Use the supplied personal evidence only when relevant; never invent personal facts. "
                            "For general questions, use your general knowledge. Be concise, usually 1-3 sentences. "
                            "Return only the reply, without analysis, internal reports, source paths or profile summaries."),
                    max_tokens=480).strip()
                if not answer:
                    raise LLMUnavailable("The model returned an empty reply. Please retry.")
                return answer, "", None, 0.0, True
            except LLMUnavailable as exc:
                log.warning("Chat provider unavailable: %s", exc)
                raise LLMUnavailable("The answer service is temporarily unavailable. Please retry.") from exc
            finally:
                self.llm.on_text = preview
        sys = (
            f"You are the digital twin of {self.profile.name if self.profile else 'the person'}. "
            "You answer as the person would (first person, their voice) based ONLY on the "
            "given profile and evidence. Do not invent preferences. Be specific and honest "
            "about uncertainty. Answer the actual question directly; do not include profile "
            "summaries, internal reports, source paths, or model diagnostics in the answer. "
            "Use personal evidence only when relevant to the question. Respond in JSON."
        )
        brief_toks = tokens(brief)
        brief_budget = max(2048, self.cfg.llm_context_tokens - 8192)
        bounded_brief = " ".join(brief_toks[:brief_budget]) if len(brief_toks) > brief_budget else brief
        opt_block = "\n".join(f"- {o}" for o in options) if options else "none supplied"
        user = (
            f"Question the person is facing: {question}\n"
            f"Options: \n{opt_block}\n\n"
            "Decision brief (persona + evidence):\n"
            f"{bounded_brief}\n\n"
            "Return JSON with keys:\n"
            '  "answer": write this key FIRST; a concise 1-2 sentence first-person reply.\n'
            '  "reasoning": 1-2 sentences citing the most relevant evidence.\n' 
            '  "best": the exact option text they would most likely pick; if options were '
            "none supplied, write the action they'd take; if truly unknowable, \"\" .\n"
            '  "confidence": 0.0 to 1.0\n'
            "Only use evidence present in the brief. Match the question's language. "
            "Keep the entire JSON under 180 words."
        )
        try:
            data = self.llm.complete_json(
                [{"role": "system", "content": sys}, {"role": "user", "content": user}],
                temperature=0.3, max_tokens=480)
        except LLMUnavailable:
            return *self._template_answer(question, options, brief), False
        except Exception as e:  # noqa: BLE001
            log.warning("reason failed: %s", e)
            return *self._template_answer(question, options, brief), False
        if not isinstance(data, dict):
            return *self._template_answer(question, options, brief), False
        reasoning = str(data.get("reasoning", "")).strip()
        answer = str(data.get("answer", reasoning)).strip()
        best = str(data.get("best", "")).strip() if data.get("best") else None
        if best and options:
            # match to an original option (case-insensitive prefix)
            for o in options:
                if best.lower() in o.lower() or o.lower() in best.lower():
                    best = o
                    break
            else:
                best = None
        try:
            conf = float(data.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        if not answer and reasoning:
            answer = reasoning
        if not answer:
            return *self._template_answer(question, options, brief), False
        return answer, reasoning, best, min(max(conf, 0.0), 1.0), True

    def _template_answer(self, question, options, brief):
        if options:
            return (f"Based on the evidence in my profile, I'd weigh {', '.join(options)} "
                    "against my usual decision rules. Check reasoning for the closest pattern.",
                    "Template reasoning: I tend to follow my stated preferences and "
                    "decision rules above; no external LLM was available for a "
                    "first-person narrative.", None, 0.5)
        return ("The answer service is unavailable right now. Please try again later.",
                "No LLM configured.", None, 0.0)