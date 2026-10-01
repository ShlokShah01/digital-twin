"""Assemble a Profile (the digital twin's memory) from style stats, extracted
preferences/patterns/facts, and a persona. Persona is LLM-written when possible,
template-generated otherwise."""

from __future__ import annotations

import json
from pathlib import Path

from .llm import ChatClient, LLMUnavailable
from .models import Chunk, Profile, StyleProfile
from .text_utils import text_terms

_PERSONA_SYSTEM = (
    "You profile one person from their own writing. Be concrete, neutral and "
    "specific. Never invent. Output plain prose (no markdown), first person."
)


def _formality_words(s: StyleProfile) -> str:
    if s.formality >= 0.6:
        return "formally and carefully"
    if s.formality <= 0.35:
        return "casually and conversationally"
    return "in a relaxed, mid-formal register"


def build_persona(profile_seed: dict, llm: ChatClient | None) -> str:
    if llm is not None and llm.enabled:
        prompt = (
            "Using ONLY the facts below about a person, write a first-person "
            "profile of 140-190 words that captures how they think, what they "
            "value, how they decide, and their communication style. First person "
            "(\"I...\"). Be concrete and grounded.\n\n"
            + json.dumps(profile_seed, indent=1)[:5000]
        )
        try:
            text = llm.complete_text(prompt, system=_PERSONA_SYSTEM, temperature=0.4, max_tokens=600)
            if text and len(text.split()) >= 30:
                return text.strip()
        except LLMUnavailable:
            pass
        except Exception:  # noqa: BLE001
            pass
    return _template_persona(profile_seed)


def _template_persona(seed: dict) -> str:
    s = seed.get("style") or {}
    name = seed.get("name") or "this person"
    parts = [f"This is a twin of {name} built from their own writing."]
    mean_sl = s.get("mean_sentence_len", 0)
    if mean_sl:
        parts.append(f"Typical sentences run about {mean_sl:.0f} words.")
    topw = [w for w, _ in (s.get("top_words") or [])[:6]]
    if topw:
        parts.append(f"Recurring words include {', '.join(topw)}.")
    prefs = seed.get("preferences") or []
    if prefs:
        lines = []
        for p in prefs[:5]:
            stance = {"positive": "likes", "negative": "avoids", "neutral": "is neutral on"}.get(p.get("stance"), "notes")
            lines.append(f"- {stance} {p.get('domain') or 'n/a'}: {p.get('statement', '')[:120]}")
        parts.append("Notable preferences:\n" + "\n".join(lines))
    patterns = seed.get("decision_patterns") or []
    if patterns:
        parts.append("Recurring decision rules:\n" + "\n".join(
            f"- {p.get('name', '')[:80]}" for p in patterns[:4]))
    topics = seed.get("topics") or []
    if topics:
        parts.append("Dominant topics in their writing: " + ", ".join(t for t, _ in topics[:8]) + ".")
    return "\n".join(parts)


def assemble_profile(
    *,
    name_guess: str,
    style: StyleProfile,
    preferences,
    decision_patterns,
    facts,
    entities,
    chunks: list[Chunk],
    llm: ChatClient | None,
    built_at: str,
) -> Profile:
    topics = _top_topics(chunks, n=14)
    seed = {
        "name": name_guess or "this person",
        "style": style.model_dump(),
        "preferences": [p.model_dump() for p in preferences],
        "decision_patterns": [p.model_dump() for p in decision_patterns],
        "topics": topics,
    }
    persona = build_persona(seed, llm)
    guardrails = [
        "Answer in the first person, as this person would think and talk.",
        "Ground every claim in the evidence; never invent a preference that is not in the profile.",
        "If the evidence is weak or conflicting, say so and give the closest pattern instead of a confident guess.",
        "Prefer concrete reasons ('because I value X / I usually Y') over generic advice.",
    ]
    return Profile(
        name=name_guess or "this person",
        persona=persona,
        style=style,
        preferences=preferences,
        decision_patterns=decision_patterns,
        facts=facts,
        entities=entities,
        topics=topics,
        guardrails=guardrails,
        built_at=built_at,
        stats={
            "n_documents": len({c.doc_id for c in chunks}),
            "n_chunks": len(chunks),
            "n_words": style.n_words,
            "n_facts": len(facts),
            "n_preferences": len(preferences),
            "n_patterns": len(decision_patterns),
            "n_entities": len(entities),
        },
    )


def _top_topics(chunks: list[Chunk], n: int = 14) -> list[tuple[str, float]]:
    from collections import Counter
    counter: Counter[str] = Counter()
    for c in chunks:
        for t in set(text_terms(c.text)):
            counter[t] += 1
    n_docs = max(len(chunks), 1)
    scored = [(t, v / n_docs) for t, v in counter.most_common(n)]
    return scored


def save_profile(profile: Profile, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")


def load_profile(path: Path) -> Profile | None:
    if not path.exists():
        return None
    try:
        return Profile.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None