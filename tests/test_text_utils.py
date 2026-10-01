from digital_twin.text_utils import (
    clean, chunk_text, count_emojis, idf, normalize_label, sentences,
    sentiment_lexicon, text_terms, tokens, top_keywords, words,
)


def test_tokens_and_words():
    assert "hello" in words("hello, world!")
    assert "!" in tokens("hello!")
    assert not words("!!!")
    assert words("can't stop") == ["can't", "stop"]


def test_sentences_split():
    s = sentences("First one. Second two! Is this three?")
    assert len(s) == 3
    assert s[0] == "First one."


def test_clean_normalizes_whitespace():
    assert clean("a\n\n b   c") == "a b c"
    assert clean("") == ""


def test_text_terms_filters():
    terms = text_terms("the cat and the very long keyboard")
    assert "cat" in terms
    assert "the" not in terms
    assert "and" not in terms
    assert "keyboard" in terms


def test_chunk_overlap_spans_chunks():
    body = " ".join(f"Word{i}." for i in range(120))
    chunks = chunk_text(body, chunk_words=20, overlap=5)
    assert len(chunks) >= 2
    assert chunks[0] != chunks[1]
    # tail of the first chunk should appear in the second (overlap)
    tail = " ".join(chunks[0].split()[-3:])
    assert tail in chunks[1]


def test_chunk_never_empty_and_respects_approx_limit():
    body = "Sentence one here. " * 400
    chunks = chunk_text(body, chunk_words=50, overlap=10)
    assert all(c.strip() for c in chunks)
    assert all(len(c.split()) <= 55 for c in chunks)


def test_normalize_label_slug():
    assert normalize_label("Buy the New 16-inch, Now!") == "buy_the_new_16_inch_now"
    assert normalize_label("   ") == "option"


def test_idf_discriminates():
    m = idf([{"cat", "meow"}, {"dog"}, {"cat"}])
    assert m["cat"] < m["dog"]  # rarer term gets higher weight


def test_sentiment_lexicon():
    mean, pos, neg = sentiment_lexicon("I love this durable bike")
    assert mean > 0 and pos >= 1 and neg == 0
    mean2, pos2, neg2 = sentiment_lexicon("this was a terrible waste")
    assert mean2 < 0 and neg2 >= 1


def test_emoji_count():
    assert count_emojis("hi 😀 and 🚲") == 2
    assert count_emojis("no emoji") == 0


def test_top_keywords_orders_by_tfidf():
    tf = {"a": 10, "b": 1}
    kws = top_keywords(tf, {"a": 2.0, "b": 2.0}, k=2)
    assert kws[0] == "a"