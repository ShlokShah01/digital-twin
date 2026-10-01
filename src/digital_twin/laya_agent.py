"""Laya adapter - the decision model used as:
  * a choice classifier:  "Which of these options would the person pick?"
  * a chunk reranker:     "Is this passage relevant to the query?"

Laya is non-autoregressive (no text generation, no hallucinated parse errors)
and returns calibrated probabilities. The checkpoint defaults to
`typed-decisions` (1024-token context) which fits a decision brief + options.

Note on Windows: MLX (Apple Silicon) cannot run here, so we use the official
cross-platform `laya` package (transformers/torch). On Apple Silicon you can
point this adapter at laya-mlx behind the same two methods."""

from __future__ import annotations

import logging
import threading
from functools import lru_cache
from typing import Any, Sequence

log = logging.getLogger(__name__)
_LOAD_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _cached_agent(model_id: str, checkpoint: str, device: str):
    import laya
    kwargs = {"device": device}
    if checkpoint and checkpoint not in ("english", "default", ""):
        kwargs["subfolder"] = checkpoint
    return laya.load(model_id, **kwargs)


class LayaEngine:
    def __init__(self, checkpoint: str = "typed-decisions", device: str = "cpu",
                 model_id: str = "convaiinnovations/laya", enabled: bool = True):
        self.checkpoint = checkpoint
        self.device = device
        self.model_id = model_id
        self.enabled = enabled
        self._agent = None
        self._load_error: str | None = None

    # -------------------------------------------------------------------------
    @property
    def available(self) -> bool:
        if not self.enabled:
            return False
        if self._agent is not None:
            return True
        if self._load_error is not None:
            return False
        return True

    def _load(self):
        if not self.enabled:
            self._load_error = self._load_error or "disabled by DIGITAL_TWIN_NO_LAYA"
            return None
        if self._agent is not None:
            return self._agent
        if self._load_error is not None:
            return None
        try:
            # Share weights across request engines; serialize initial GPU allocation.
            with _LOAD_LOCK:
                self._agent = _cached_agent(self.model_id, self.checkpoint, self.device)
        except Exception as e:  # noqa: BLE001
            self._load_error = str(e)
            log.warning("Laya failed to load (%s) - choice/rerank steps will be skipped", e)
            self._agent = None
        return self._agent

    # -------------------------------------------------------------------------
    # classifier: what would this person choose?
    # -------------------------------------------------------------------------
    def predict_choice(self, state: str, options: Sequence[str],
                       instructions: str | None = None) -> dict[str, Any] | None:
        """Score every option in one forward pass.

        Uses the model's strongest primitive: a per-option `noul` question
        ("would this person pick THIS option, given who they are?") whose
        P(true) answers are normalized into a probability distribution. A
        single multi-label `choice` question runs in the same pass as a
        cross-check (Laya's choice logits drift toward option wording; noul is
        measurably more evidence-sensitive - see docstring in README).

        Returns:
          {choice, probabilities (noul-normalized), confidence, noul, choice_probs}
        or None when Laya is unavailable.
        """
        agent = self._load()
        if agent is None or not options:
            return None
        options = [str(o) for o in options]
        if len(options) < 2:
            return None  # a single option makes any vote meaningless (P(true)=1)
        instructions = instructions or (
            "Which option is this person most likely to choose, given who they "
            "are, how they think and what they have done before?"
        )
        state_text = _fit_state(state, max_chars=5000)

        questions: dict[str, Any] = {}
        if len(options) <= 8:
            # choice question (cross-check). Opaque-but-read semantic labels.
            criteria = {}
            for i, opt in enumerate(options):
                lab = f"option_{i}"
                criteria[lab] = opt
            questions["prediction"] = {
                "type": "choice",
                "instructions": instructions,
                "criteria": criteria,
            }
        # per-option noul (primary signal)
        for i, opt in enumerate(options):
            questions[f"noul_{i}"] = {
                "type": "noul",
                "instructions": (
                    f"Given who this person is, how they think and their past "
                    f"decisions, would they most likely choose this option? "
                    f"Option: {opt}"
                ),
                "criteria": {
                    "false": "they would not choose this option",
                    "true": "they would likely choose this option",
                },
            }
        try:
            res = agent.predict({"state": state_text}, questions)
        except Exception as e:  # noqa: BLE001
            log.warning("Laya predict failed: %s", e)
            return None

        answers = res.get("answers") or {}

        # primary: noul-normalized distribution
        raw_noul: dict[str, float] = {}
        for i, opt in enumerate(options):
            ans = answers.get(f"noul_{i}") or {}
            p = ans.get("noul")
            raw_noul[opt] = float(p) if isinstance(p, (int, float)) else 0.0
        denom = sum(raw_noul.values())
        probabilities = {opt: (p / denom) if denom else 0.0
                         for opt, p in raw_noul.items()}
        if not probabilities or denom == 0:
            return None

        # cross-check: multi-label choice logits
        choice_probs: dict[str, float] = {}
        if "prediction" in answers:
            ans = answers["prediction"] or {}
            probs = ans.get("probabilities") or {}
            for key, p in probs.items():
                idx = int(key.rsplit("_", 1)[-1]) if key.startswith("option_") else -1
                if 0 <= idx < len(options):
                    choice_probs[options[idx]] = float(p)

        top_opt = max(probabilities, key=probabilities.get)
        confidence = probabilities[top_opt]
        return {
            "choice": top_opt,
            "probabilities": probabilities,
            "confidence": confidence,
            "noul": raw_noul,
            "choice_probs": choice_probs,
        }

    # -------------------------------------------------------------------------
    # reranker: reorder retrieved chunks by Laya-judged relevance
    # -------------------------------------------------------------------------
    def rerank(self, query: str, passages: Sequence[str], top_k: int = 6,
               batch_size: int = 8) -> list[int] | None:
        """Return indices into `passages` sorted by relevance (best first),
        truncated to top_k. None when Laya is unavailable."""
        agent = self._load()
        if agent is None or not passages:
            return None
        states = [{"query": query, "passage": _fit_passage(p)} for p in passages]
        questions = {
            "relevant": {
                "type": "choice",
                "instructions": (
                    "Does this passage provide real, specific evidence about "
                    "this person that is useful for answering the query?"
                ),
                "criteria": {
                    "relevant_evidence": "the passage is about this person and helps answer the query",
                    "unrelated": "the passage is generic, off-topic or not about this person",
                },
            },
        }
        try:
            results = agent.predict_batch(states, questions, batch_size=batch_size)
        except Exception as e:  # noqa: BLE001
            log.warning("Laya rerank failed: %s", e)
            return None

        scores: list[float] = []
        for r in results:
            ans = (r.get("answers") or {}).get("relevant") or {}
            probs = ans.get("probabilities") or {}
            p = probs.get("relevant_evidence")
            if p is None:
                p = ans.get("answer_confidence") or ans.get("noul") or 0.0
            scores.append(float(p))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return order[:top_k] if top_k else order


def _fit_state(state: str, max_chars: int = 5000) -> str:
    """typed-decisions uses 1024 ctx with ~256 reserved for option labels."""
    state = state.strip()
    if len(state) <= max_chars:
        return state
    return state[:max_chars] + " ..."


def _fit_passage(p: str, max_chars: int = 900) -> str:
    p = p.strip()
    return p if len(p) <= max_chars else p[:max_chars] + " ..."