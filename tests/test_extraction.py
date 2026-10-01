from digital_twin.extraction import (
    decision_patterns_from, entities_from, facts_from,
    merge_entities, merge_patterns, merge_preferences,
    offline_extract, preferences_from,
)

LLM_OUT = {
    "name_guess": "Alex Carter",
    "entities": [
        {"name": "Sam", "type": "person", "note": "friend"},
        {"name": "Loop Labs", "type": "org", "note": ""},
    ],
    "preferences": [
        {"domain": "laptop", "stance": "positive",
         "statement": "prefers refurbished with a warranty", "strength": 0.9,
         "examples": ["laptop"]},
    ],
    "decision_patterns": [
        {"name": "two-week wait", "trigger": "purchases",
         "behavior": "waits two weeks before deciding", "examples": ["laptop"]},
    ],
    "facts": [
        {"text": "waits two weeks before buying", "category": "decision"},
    ],
}


def test_llm_shaped_outputs_parse():
    ents = entities_from(LLM_OUT)
    assert len(ents) == 2
    assert ents[0].id.startswith("ent:")
    assert ents[0].type == "person"

    prefs = preferences_from(LLM_OUT)
    assert len(prefs) == 1
    assert prefs[0].stance == "positive"

    pats = decision_patterns_from(LLM_OUT)
    assert len(pats) == 1
    assert pats[0].name == "two-week wait"

    facts = facts_from(LLM_OUT)
    assert len(facts) >= 1


def test_merges_dedupe_by_semantics():
    one = preferences_from(LLM_OUT)
    merged = merge_preferences([], one + preferences_from(LLM_OUT))
    assert len(merged) == len(one)

    pats = decision_patterns_from(LLM_OUT)
    assert len(merge_patterns([], pats + pats)) == len(pats)

    ents = entities_from(LLM_OUT)
    assert len(merge_entities([], ents + ents)) == len(ents)


def test_offline_extract_finds_signal():
    snippet = (
        "I prefer refurbished laptops over brand new flagship models. "
        "I avoid loud restaurants and crowded bars. "
        "My rule: two-week wait for any purchase over two hundred dollars. "
        "I rather write an email than answer a phone call."
    )
    out = offline_extract(snippet)
    assert isinstance(out, dict)
    assert set(out) >= {"name_guess", "entities", "relations", "preferences",
                        "decision_patterns", "facts"}
    assert out["preferences"], "expected mined preferences"
    assert out["decision_patterns"], "expected a mined decision rule"
    assert any("wait" in (p.get("behavior") or "") for p in out["decision_patterns"])


def test_mine_entities_capitalised():
    snippet = "Last week I met Sam at Pony's Coffee in Portland."
    out = offline_extract(snippet)
    names = {e.get("name", "").lower() for e in out["entities"]}
    assert {"sam", "portland"}.issubset(names) or "ponys" in names