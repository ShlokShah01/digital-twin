"""Pydantic models shared across the twin."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data model (what gets ingested / stored)
# ---------------------------------------------------------------------------
class Document(BaseModel):
    doc_id: str
    title: str
    source: str  # file path
    kind: str = "text"  # text | json | csv | markdown
    text: str


class Chunk(BaseModel):
    id: str
    doc_id: str
    source: str
    title: str
    text: str
    n_tokens: int = 0
    keywords: list[str] = Field(default_factory=list)


class StyleProfile(BaseModel):
    n_documents: int = 0
    n_words: int = 0
    n_sentences: int = 0
    n_chunks: int = 0
    mean_sentence_len: float = 0.0
    median_sentence_len: float = 0.0
    longest_sentence: int = 0
    mean_word_len: float = 0.0
    vocabulary: int = 0
    ttr: float = 0.0  # type-token ratio on a bounded sample
    top_words: list[tuple[str, int]] = Field(default_factory=list)
    top_bigrams: list[tuple[str, int]] = Field(default_factory=list)
    punctuation: dict[str, float] = Field(default_factory=dict)  # per 100 words
    emoji_count: int = 0
    emoji_per_1000: float = 0.0
    sentence_caps: float = 0.0  # fraction of sentences starting with a capital
    allcaps_fraction: float = 0.0
    fillers: dict[str, int] = Field(default_factory=dict)
    hedges: dict[str, int] = Field(default_factory=dict)
    sentiment_mean: float = 0.0
    sentiment_positive: float = 0.0
    sentiment_negative: float = 0.0
    first_person_rate: float = 0.0  # pronouns per 100 words
    second_person_rate: float = 0.0
    third_person_rate: float = 0.0
    contraction_rate: float = 0.0  # contractions per 100 words
    formality: float = 0.0  # 0 casual .. 1 formal (heuristic)
    decisiveness_tokens: dict[str, int] = Field(default_factory=dict)  # always/never/hate/prefer...


class Preference(BaseModel):
    domain: str
    stance: str  # positive | negative | neutral
    statement: str
    strength: float = 0.5
    examples: list[str] = Field(default_factory=list)


class DecisionPattern(BaseModel):
    name: str
    trigger: str = ""
    behavior: str
    examples: list[str] = Field(default_factory=list)


class Entity(BaseModel):
    id: str
    name: str
    type: str = "concept"
    note: str = ""
    mentions: int = 1


class Fact(BaseModel):
    id: str
    text: str
    category: str = "note"  # preference | decision | value | identity | habit | note
    chunk_id: str = ""
    entity_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.6


class Profile(BaseModel):
    name: str = "the person"
    persona: str = ""
    style: StyleProfile = Field(default_factory=StyleProfile)
    preferences: list[Preference] = Field(default_factory=list)
    decision_patterns: list[DecisionPattern] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    topics: list[tuple[str, float]] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    built_at: str = ""
    stats: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Knowledge graph
# ---------------------------------------------------------------------------
class GraphNode(BaseModel):
    id: str
    label: str
    kind: str  # chunk | keyword | entity
    meta: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    src: str
    tgt: str
    weight: float = 1.0
    kind: str = "co"  # kw | sim | mention | rel | cooccur
    label: str = ""


class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    communities: dict[str, list[str]] = Field(default_factory=dict)  # comm_id -> node ids
    chunk_community: dict[str, str] = Field(default_factory=dict)  # chunk_id -> comm_id


# ---------------------------------------------------------------------------
# Answers
# ---------------------------------------------------------------------------
class SourceHit(BaseModel):
    chunk_id: str
    source: str
    snippet: str
    score: float = 0.0


class ChoiceOutcome(BaseModel):
    option: str
    probability: float = 0.0
    rank: int = 0


class Answer(BaseModel):
    question: str
    choice: str | None = None
    choices: list[ChoiceOutcome] = Field(default_factory=list)
    confidence: float = 0.0
    answer: str = ""
    reasoning: str = ""
    sources: list[SourceHit] = Field(default_factory=list)
    graph_context: bool = False
    model: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)