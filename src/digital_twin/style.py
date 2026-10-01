"""NLP style analysis: turns raw text into a StyleProfile of writing/speaking
habits - frequent words and bigrams, sentence rhythm, punctuation, emoji use,
hedging vs. decisive language, sentiment, pronouns and a formality heuristic."""

from __future__ import annotations

import math
import statistics

from .models import StyleProfile
from .text_utils import (
    DECISIVE,
    FILLERS,
    HEDGES,
    _CAPS_START,
    _CONTRACTIONS,
    _ALLCAPS,
    count_emojis,
    sentences,
    sentiment_lexicon,
    text_terms,
    token_count,
    tokens,
    words,
)


def _bigrams(ws: list[str], n: int = 15):
    seen: dict[tuple[str, str], int] = {}
    for a, b in zip(ws, ws[1:]):
        key = (a, b)
        seen[key] = seen.get(key, 0) + 1
    top = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [(" ".join(k), v) for k, v in top]


def analyze_style(text: str, n_chunks: int = 0) -> StyleProfile:
    n_words_total = len(words(text))
    sents = sentences(text)

    # --- core rhythm -------------------------------------------------------
    sent_lens = [max(len(words(s)), 1) for s in sents]
    mean_sl = statistics.fmean(sent_lens) if sent_lens else 0.0
    med_sl = statistics.median(sent_lens) if sent_lens else 0.0
    longest_s = max(sent_lens, default=0)

    word_lens = [len(w) for w in words(text)]
    mean_wl = statistics.fmean(word_lens) if word_lens else 0.0

    # --- vocabulary --------------------------------------------------------
    all_terms = text_terms(text)
    vocab = len(set(all_terms))
    sample = all_terms[:2000]
    ttr = (len(set(sample)) / len(sample)) if sample else 0.0
    top_freqs: dict[str, int] = {}
    for t in all_terms:
        top_freqs[t] = top_freqs.get(t, 0) + 1
    top_words = sorted(top_freqs.items(), key=lambda kv: kv[1], reverse=True)[:20]

    top_bigrams = _bigrams([w.lower() for w in words(text)])

    # --- punctuation (per 100 words) --------------------------------------
    nw = max(n_words_total, 1)
    punct: dict[str, float] = {}
    for mark in ["!", "?", "...", ";", "—", ",", "'", '"']:
        punct[mark] = round(text.count(mark) / nw * 100.0, 3)

    # --- emoji -------------------------------------------------------------
    emoji_count = count_emojis(text)
    emoji_per_1000 = round(emoji_count / nw * 1000.0, 3)

    # --- capitalization ----------------------------------------------------
    starts = [s for s in sents if s.strip()]
    sentence_caps = round(sum(1 for s in starts if _CAPS_START.match(s.strip())) / len(starts), 3) if starts else 0.0
    word_toks = tokens(text)
    allcaps = [w for w in word_toks if len(w) > 1 and w.isupper()]
    allcaps_fraction = round(len(allcaps) / len(word_toks), 4) if word_toks else 0.0

    # --- fillers / hedges / decisive tokens ---------------------------------
    low = text.lower()
    fillers: dict[str, int] = {f: low.count(f) for f in FILLERS if f in low}
    hedges: dict[str, int] = {h: low.count(h) for h in HEDGES if h in low}
    decisive: dict[str, int] = {d: low.count(d) for d in DECISIVE if d in low}
    total_fillers = sum(fillers.values())
    total_hedges = sum(hedges.values())
    total_decisive = sum(decisive.values())

    # --- sentiment ---------------------------------------------------------
    mean_sent, npos, nneg = sentiment_lexicon(text)
    sentiment_positive = round(npos / nw * 100.0, 3)
    sentiment_negative = round(nneg / nw * 100.0, 3)

    # --- pronouns ------------------------------------------------------------
    from .text_utils import PRONOUNS_1, PRONOUNS_2, PRONOUNS_3

    first_person_rate = round(len(PRONOUNS_1.findall(text)) / nw * 100.0, 3)
    second_person_rate = round(len(PRONOUNS_2.findall(text)) / nw * 100.0, 3)
    third_person_rate = round(len(PRONOUNS_3.findall(text)) / nw * 100.0, 3)
    contraction_rate = round(len(_CONTRACTIONS.findall(text)) / nw * 100.0, 3)

    # --- formality heuristic (0 casual .. 1 formal) --------------------------
    exclam = punct.get("!", 0)
    c1 = max(0.0, 1.0 - total_fillers / max(nw, 1) * 4.0)         # fewer fillers -> formal
    c2 = max(0.0, 1.0 - exclam / 4.0)                              # fewer ! -> formal
    c3 = max(0.0, 1.0 - contraction_rate / 4.0)                    # fewer contractions -> formal
    c4 = min(1.0, mean_wl / 5.0)                                   # longer words -> formal
    c5 = max(0.0, 1.0 - allcaps_fraction / 0.05)                   # less caps -> formal
    formality = round((c1 + c2 + c3 + c4 + c5) / 5.0, 3)

    return StyleProfile(
        n_chunks=n_chunks,
        n_words=n_words_total,
        n_sentences=len(sents),
        mean_sentence_len=round(mean_sl, 2),
        median_sentence_len=round(med_sl, 2),
        longest_sentence=longest_s,
        mean_word_len=round(mean_wl, 2),
        vocabulary=vocab,
        ttr=round(ttr, 4),
        top_words=top_words,
        top_bigrams=top_bigrams,
        punctuation=punct,
        emoji_count=emoji_count,
        emoji_per_1000=emoji_per_1000,
        sentence_caps=sentence_caps,
        allcaps_fraction=allcaps_fraction,
        fillers=fillers,
        hedges=hedges,
        sentiment_mean=round(mean_sent, 3),
        sentiment_positive=sentiment_positive,
        sentiment_negative=sentiment_negative,
        first_person_rate=first_person_rate,
        second_person_rate=second_person_rate,
        third_person_rate=third_person_rate,
        contraction_rate=contraction_rate,
        formality=formality,
        decisiveness_tokens=decisive,
    )