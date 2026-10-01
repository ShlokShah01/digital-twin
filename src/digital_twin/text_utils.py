"""Small, dependency-free text utilities: tokenization, sentence splitting,
chunking, keyword helpers and a compact sentiment lexicon."""

from __future__ import annotations

import math
import re

_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[A-Za-z0-9']+|[^\w\s]")

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9']*$")

STOPWORDS = set(
    """a an and are as at be but by can could did do does for from get got
    had has have he her hers him his how i if in into is it its just like me
    more most my no not of on or our out over said so some than that the their
    them then there these they this those through to too up us very was we were
    what when where which who why will with would you your yours am been being
    did do does doing done down during each few have them it's i'm don't can't
    you're we're there's that's what's here's shall should may might must""".split()
)

FILLERS = ["um", "uh", "er", "hmm", "like", "you know", "i mean", "basically", "actually", "literally"]
HEDGES = ["maybe", "probably", "perhaps", "possibly", "i think", "i guess", "kind of", "sort of", "could", "might", "somewhat"]
DECISIVE = ["always", "never", "hate", "love", "refuse", "prefer", "would rather", "only", "best", "worst", "avoid", "require", "must", "insist"]

_CONTRACTIONS = re.compile(r"\b(?:can't|won't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't|i'm|i've|i'll|i'd|you're|you've|you'll|we're|we've|we'll|they're|they've|that's|it's|he's|she's|there's|let's|what's|who's)\b", re.I)

PRONOUNS_1 = re.compile(r"\b(i|me|my|mine|myself|we|us|our|ours|i'm|i've|i'll|i'd)\b", re.I)
PRONOUNS_2 = re.compile(r"\b(you|your|yours|yourself)\b", re.I)
PRONOUNS_3 = re.compile(r"\b(he|him|his|she|her|hers|it|its|they|them|their|theirs)\b", re.I)

_CAPS_START = re.compile(r"^[A-Z]")
_ALLCAPS = re.compile(r"^[A-Z0-9'!?.,;: -]+$")

_EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
    "\U0001FA80-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF]+"
)

_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


# ---------------------------------------------------------------------------
# tokens / words / sentences
# ---------------------------------------------------------------------------
def clean(text: str) -> str:
    if not text:
        return ""
    text = _WS.sub(" ", text.replace("\r", "\n")).strip()
    return text


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text or "")]


def words(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text or "") if _WORD.match(t)]


def sentences(text: str) -> list[str]:
    text = clean(text)
    if not text:
        return []
    parts = _SENT_BOUNDARY.split(text)
    out = []
    for p in parts:
        p = p.strip()
        if p:
            out.append(p)
    return out


def word_count(text: str) -> int:
    return len(words(text))


def token_count(text: str) -> int:
    return len(tokens(text))


def normalize_label(text: str, max_len: int = 40) -> str:
    """Turn an arbitrary option string into a semantic but slug-safe label.
    (Laya follows opaque labels; we keep them readable yet distinct.)"""
    s = re.sub(r"[^A-Za-z0-9]+", "_", text.strip().lower()).strip("_")
    s = re.sub(r"_+", "_", s)[:max_len].strip("_")
    return s or "option"


# ---------------------------------------------------------------------------
# chunking
# ---------------------------------------------------------------------------
def chunk_text(text: str, chunk_words: int = 220, overlap: int = 40) -> list[str]:
    """Sentence-aware chunking with word-overlap."""
    sents = sentences(text)
    if not sents:
        return []
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for s in sents:
        s_len = max(word_count(s), 1)
        if cur and cur_len + s_len > chunk_words:
            chunks.append(" ".join(cur))
            back = []
            b_len = 0
            for prev in reversed(cur):
                p = max(word_count(prev), 1)
                if b_len + p > overlap:
                    break
                back.insert(0, prev)
                b_len += p
            cur = back
            cur_len = b_len
        cur.append(s)
        cur_len += s_len
    if cur:
        chunks.append(" ".join(cur))
    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# keyword / TF-IDF helpers
# ---------------------------------------------------------------------------
def text_terms(text: str) -> list[str]:
    out = []
    for w in words(text.lower()):
        if w not in STOPWORDS and len(w) > 2 and not w.isdigit():
            out.append(w)
    return out


def term_freqs(terms: list[str]) -> dict[str, int]:
    freqs: dict[str, int] = {}
    for t in terms:
        freqs[t] = freqs.get(t, 0) + 1
    return freqs


def idf(corpus_term_sets: list[set[str]]) -> dict[str, float]:
    n = len(corpus_term_sets)
    df: dict[str, int] = {}
    for ts in corpus_term_sets:
        for t in ts:
            df[t] = df.get(t, 0) + 1
    return {t: math.log((n + 1) / (v + 1)) + 1.0 for t, v in df.items()}


def top_keywords(tf: dict[str, int], idf_map: dict[str, float], k: int = 6) -> list[str]:
    scored = [(t, tf.get(t, 0) * idf_map.get(t, 1.0)) for t in tf]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in scored[:k]]


# ---------------------------------------------------------------------------
# a small AFINN-style sentiment lexicon (inline, no downloads)
# ---------------------------------------------------------------------------
SENTIMENT: dict[str, float] = {
    "love": 3, "loved": 3, "best": 3, "great": 3, "awesome": 3, "amazing": 3,
    "happy": 2.5, "glad": 2, "enjoy": 2, "enjoyed": 2, "like": 1.5, "liked": 1.5,
    "nice": 1.5, "good": 1.5, "better": 2, "favorite": 2, "favourite": 2,
    "awesome": 3, "perfect": 3, "recommend": 2, "highly": 1.5, "wonderful": 3,
    "excited": 2.5, "relieved": 2, "calm": 1.5, "peaceful": 2, "cozy": 1.5,
    "worth": 1.5, "reliable": 2, "durable": 1.5, "trust": 2, "trusted": 2,
    "comfortable": 1, "fine": 1, "better": 2, "win": 2, "winning": 2,
    "satisfied": 2, "confident": 1.5, "sure": 1, "freedom": 1.5, "simple": 0.5,
    "minimal": 0.5, "clean": 0.5, "fun": 1.5,
    "hate": -3, "hated": -3, "worst": -3, "terrible": -3, "awful": -3,
    "bad": -2, "worse": -2.5, "sad": -2, "angry": -2.5, "frustrated": -2.5,
    "annoying": -2, "annoyed": -2, "dislike": -2, "disappointed": -2.5,
    "expensive": -1.5, "overpriced": -2, "rip-off": -3, "scam": -3,
    "waste": -2, "regret": -2.5, "regretted": -2.5, "stress": -2, "stressed": -2.5,
    "anxious": -2, "worried": -2, "fear": -2, "scared": -2, "tired": -1.5,
    "exhausted": -2, "boring": -1.5, "bored": -1.5, "dread": -2.5,
    "fail": -2, "failed": -2, "broken": -2, "refuse": -2, "refused": -2,
    "problem": -1.5, "issue": -1, "trouble": -2, "delay": -1, "delayed": -1.5,
    "cancelled": -1.5, "cancel": -1.5, "censored": -2, "chaos": -2,
    "guilt": -1.5, "guilty": -1.5, "hurt": -2, "pain": -2, "worry": -1.5,
    "confused": -1.5, "mess": -1.5, "chaotic": -2, "loud": -1, "noisy": -1,
    "crowded": -1, "busy": -0.5, "sales": 0.5, "sale": 0.5, "discount": 1,
    "deal": 1, "budget": 0.5, "cheap": 0, "frugal": 0.5, "saving": 1,
    "save": 1, "saved": 1.5, "secondhand": 0.5, "used": 0, "reuse": 1,
    "repair": 1, "fix": 1, "fixing": 1, "cook": 1, "cooking": 1, "homemade": 1,
    "plant": 0.5, "garden": 1, "outdoors": 1, "hike": 1, "cycling": 1.5,
    "bike": 1, "coffee": 1, "tea": 1, "read": 1, "reading": 1.5, "books": 1,
    "quiet": 1, "solitude": 1, "alone": 0, "introvert": 0.5,
}


def sentiment_lexicon(text: str) -> tuple[float, int, int]:
    """Return (mean valence, n_positive, n_negative) using the inline lexicon."""
    vals: list[float] = []
    npos = nneg = 0
    for w in words(text.lower()):
        v = SENTIMENT.get(w)
        if v is None:
            continue
        vals.append(v)
        if v > 0:
            npos += 1
        elif v < 0:
            nneg += 1
    if not vals:
        return 0.0, 0, 0
    return sum(vals) / len(vals), npos, nneg


def count_emojis(text: str) -> int:
    return len(_EMOJI_PATTERN.findall(text))