from digital_twin.config import Config, load_config
from digital_twin.laya_agent import LayaEngine


def test_defaults_exist():
    c = Config()
    assert c.chunk_words >= 1
    assert c.chunk_overlap >= 0
    assert c.laya_checkpoint
    assert c.embed_model


def test_load_config():
    assert isinstance(load_config(), Config)


def test_laya_enabled_flag_is_honored():
    off = LayaEngine(enabled=False)
    assert off.available is False
    assert off.predict_choice("state", ["a", "b"]) is None
    assert off.rerank("q", ["p1", "p2"]) is None
    assert off._load() is None

    on = LayaEngine(enabled=True)
    assert on.available is True  # lazily loads, so "available" until a load attempt
    on = LayaEngine(enabled=False)
    assert on.available is False


class TestCliSplit:
    def test_semicolon_and_pipe(self):
        from digital_twin.cli import _split_options

        assert _split_options("a;b c;d") == ["a", "b c", "d"]
        assert _split_options("a|b|c") == ["a", "b", "c"]
        assert _split_options(None) == []
        assert _split_options("") == []
        assert _split_options(" ; | ") == []