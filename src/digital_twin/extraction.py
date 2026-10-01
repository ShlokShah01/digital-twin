"""Convert raw LLM extraction output into profile models (dedup, id-assign,
sanitize)."""

from __future__ import annotations

import re as _re
from collections import Counter as _Counter
from typing import Any

from .models import DecisionPattern, Entity, Fact, Preference
from .text_utils import normalize_label, text_terms


def _clean_text(s: Any) -> str:
    return str(s or "").strip()


def entities_from(data: dict) -> list[Entity]:
    out: list[Entity] = []
    for raw in data.get("entities") or []:
        name = _clean_text(raw.get("name"))
        if not name:
            continue
        out.append(Entity(
            id=f"ent:{normalize_label(name)}",
            name=name,
            type=_clean_text(raw.get("type")) or "concept",
            note=_clean_text(raw.get("note")),
            mentions=max(int(raw.get("mentions") or 1), 1),
        ))
    return out


def preferences_from(data: dict) -> list[Preference]:
    out: list[Preference] = []
    for raw in data.get("preferences") or []:
        stmt = _clean_text(raw.get("statement"))
        if not stmt:
            continue
        try:
            strength = float(raw.get("strength") or 0.5)
        except (TypeError, ValueError):
            strength = 0.5
        out.append(Preference(
            domain=_clean_text(raw.get("domain")) or "general",
            stance=_clean_text(raw.get("stance")) or "neutral",
            statement=stmt,
            strength=min(max(strength, 0.0), 1.0),
            examples=[_clean_text(e) for e in (raw.get("examples") or []) if _clean_text(e)],
        ))
    return out


def decision_patterns_from(data: dict) -> list[DecisionPattern]:
    out: list[DecisionPattern] = []
    for raw in data.get("decision_patterns") or []:
        behavior = _clean_text(raw.get("behavior"))
        if not behavior:
            continue
        out.append(DecisionPattern(
            name=_clean_text(raw.get("name")) or behavior[:48],
            trigger=_clean_text(raw.get("trigger")),
            behavior=behavior,
            examples=[_clean_text(e) for e in (raw.get("examples") or []) if _clean_text(e)],
        ))
    return out


def facts_from(data: dict, chunk_id: str = "", entity_ids: list[str] | None = None) -> list[Fact]:
    out: list[Fact] = []
    for raw in data.get("facts") or []:
        text = _clean_text(raw.get("text"))
        if not text:
            continue
        out.append(Fact(
            id=f"f{len(out)}",
            text=text,
            category=_clean_text(raw.get("category")) or "note",
            chunk_id=chunk_id,
            entity_ids=entity_ids or [],
        ))
    return out


def merge_preferences(acc: list[Preference], new: list[Preference]) -> list[Preference]:
    for p in new:
        key = normalize_label(p.domain) + "|" + normalize_label(p.statement)[:40]
        if any(normalize_label(x.domain) + "|" + normalize_label(x.statement)[:40] == key for x in acc):
            continue
        acc.append(p)
    return acc


def merge_patterns(acc: list[DecisionPattern], new: list[DecisionPattern]) -> list[DecisionPattern]:
    for p in new:
        if any(x.name == p.name for x in acc):
            continue
        acc.append(p)
    return acc


def merge_entities(acc: list[Entity], new: list[Entity]) -> list[Entity]:
    by_id = {e.id: e for e in acc}
    for e in new:
        if e.id in by_id:
            by_id[e.id].mentions += e.mentions
            if e.note and not by_id[e.id].note:
                by_id[e.id].note = e.note
        else:
            by_id[e.id] = e
    return list(by_id.values())


# ---------------------------------------------------------------------------
# Offline (no-LLM) mining: rule-based preferences / decision patterns / entities.
# This keeps the twin useful without an API key and enriches the decision brief
# that Laya/LLM read, so predictions are still evidence-grounded.
# ---------------------------------------------------------------------------
_CNT = _re.compile(r"[^A-Za-z0-9'\- ]+")
_JUNK = {"i", "im", "ill", "ive", "id", "you", "cant", "dont", "one", "would", "really", "also", "still", "just", "even", "every", "never", "always", "people", "things", "something", "someone", "actually", "honestly", "basically", "finally", "maybe", "sort", "kind", "new", "this", "that", "these"}

_PREF_RE = [
    # "I would rather X than Y"
    (_re.compile(r"would rather ([^.]{4,120}) than ([^.]{3,80})", _re.I),
     lambda m: (m.group(1), m.group(2))),
    # "I prefer X (over|to) Y"
    (_re.compile(r"prefer ([^.]{4,120}) (?:over|to) ([^.]{3,80})", _re.I),
     lambda m: (m.group(1), m.group(2))),
    # "X, not Y" / "X instead of Y"
    (_re.compile(r"(?<!I )(?:is|was|are)(?: [^.]{0,20})? ([^.]{4,110}),?\s+(?:rather than|instead of|not)\s+([^.]{3,60})", _re.I),
     lambda m: (m.group(1), m.group(2))),
]
_NEG_PREF = _re.compile(r"\b(?:never|refuse|avoid|dislike|hate|won't|cannot stand|does not like|can'?t stand)\b([^.]{4,120})", _re.I)
_POS_PREF = _re.compile(r"\b(?:love|like|enjoy|favorite|favourite|obsess(?:ed|ion)?|am a fan)\b([^.]{4,110})", _re.I)
_RULE = _re.compile(r"\b(?:rule|rule of thumb|always|never)\b[^.]{4,180}(?:\.)", _re.I)
_CONCRETE = _re.compile(r"(?:\$[0-9]+|%|\bbuy\b|\bwait\b|\bcancel\b|\bkeep\b|\bprefer\b|\breliable\b|\bdurab(?:le|ility)\b|\brefurb\w*\b|\bfive[- ]year\b|\brepair\w*\b)")

_ENT_NAME = _re.compile(r"(?<![A-Za-z])([A-Z][a-zA-Z]+(?:[ ][A-Z][a-zA-Z]+){0,2})")


def _domain_of(phrase: str) -> str | None:
    terms = [t for t in text_terms(phrase) if t not in _JUNK]
    return terms[0] if terms else None


def _clean_phrase(s: str) -> str:
    s = _CNT.sub(" ", s)
    return _re.sub(r"\s+", " ", s).strip(" ,;-")


def mine_preferences(text: str) -> list[Preference]:
    """Find explicit liking/disliking statements and 'X over Y' tradeoffs."""
    out: list[Preference] = []
    for rx, fn in _PREF_RE:
        for m in rx.finditer(text):
            better, worse = fn(m)
            better = _clean_phrase(better)
            worse = _clean_phrase(worse)
            if not better:
                continue
            out.append(Preference(
                domain=_domain_of(better) or "general",
                stance="positive",
                statement=f"prefers {better[:160]} instead of {worse[:80] if worse else 'the alternative'}",
                strength=0.7,
                examples=[m.group(0)[:200]],
            ))
    for m in _POS_PREF.finditer(text):
        phrase = _clean_phrase(m.group(1))
        if phrase and len(phrase) >= 4 and not phrase.lower().startswith(("it", "that", "this", "i ")):
            out.append(Preference(
                domain=_domain_of(phrase) or "general",
                stance="positive",
                statement=f"likes {phrase[:160]}",
                strength=0.65,
                examples=[m.group(0)[:200]],
            ))
    for m in _NEG_PREF.finditer(text):
        phrase = _clean_phrase(m.group(1))
        if phrase and len(phrase) >= 4 and not phrase.lower().startswith(("it", "that", "this", "i ", "to ", "the ")):
            out.append(Preference(
                domain=_domain_of(phrase) or "general",
                stance="negative",
                statement=f"avoids or dislikes {phrase[:160]}",
                strength=0.65,
                examples=[m.group(0)[:200]],
            ))
    seen = set()
    deduped = []
    for p in out:
        key = _domain_of(p.statement) or ""
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped


def mine_patterns(text: str) -> list[DecisionPattern]:
    """Extract rule-like sentences: 'Rule: ...', 'I always/never ... when ...',
    and other decision heuristics (wait N days, repair over replace...)."""
    out: list[DecisionPattern] = []
    for m in _RULE.finditer(text):
        sent = m.group(0)
        if _CONCRETE.search(sent):
            out.append(DecisionPattern(
                name="rule",
                behavior=sent[:180],
                trigger="when making a choice that involves money, time or commitment",
            ))
    # explicit numbered/bullet rules (e.g. "two week wait for anything above $50")
    for m in _re.finditer(r"(?i)(\b\w+[- ]week wait\b[^.]*\.|\bwait\b[^.]{4,120}because[^.]*\.|repair[^.]{4,140})", text):
        out.append(DecisionPattern(name="heuristic", behavior=m.group(1)[:180]))
    seen = set()
    deduped = []
    for p in out:
        key = p.behavior[:60]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped[:12]


def mine_entities(text: str, top: int = 14) -> list[Entity]:
    """Proper-noun-ish candidates: capitalized words mid-sentence that repeat."""
    sents = _re.split(r"(?<=[.!?])\s+", text)
    cands: _Counter[str] = _Counter()
    for s in sents:
        # drop the first capitalized token of each sentence (common nouns)
        parts = s.split()
        if parts:
            parts = parts[1:]
        s = " ".join(parts)
        for m in _ENT_NAME.finditer(s):
            name = m.group(1)
            if len(name) < 3:
                continue
            base = name.split(" ")[0].lower()
            if base in _JUNK or name.lower() in ("thai", "the", "this", "week's"):
                continue
            cands[name] += 1
    out = []
    for name, cnt in cands.most_common(top):
        if cnt < 1:
            continue
        out.append(Entity(
            id=f"ent:{_CNT.sub('_', name.lower())}",
            name=name, type="concept", note="", mentions=int(cnt)))
    return out


def offline_extract(text: str) -> dict[str, list]:
    """Mimic the shape of ChatClient.extract() so the pipeline can merge
    offline and LLM results through the same code path."""
    prefs = mine_preferences(text)
    patterns = mine_patterns(text)
    ents = mine_entities(text)
    facts: list[dict] = []
    for p in prefs:
        facts.append({"text": f"[{p.stance}] {p.statement}", "category": "preference"})
    for pat in patterns:
        facts.append({"text": pat.behavior, "category": "decision"})
    return {
        "name_guess": "",
        "entities": [e.model_dump() for e in ents],
        "relations": [],
        "preferences": [p.model_dump() for p in prefs],
        "decision_patterns": [p.model_dump() for p in patterns],
        "facts": facts,
    }