from kuralcheck.cache import Cache, make_key


def test_key_depends_on_content_and_settings() -> None:
    a = make_key("prisma", b"audio", {"format": "verbatim"})
    assert a == make_key("prisma", b"audio", {"format": "verbatim"})
    assert a != make_key("prisma", b"audio2", {"format": "verbatim"})
    assert a != make_key("prisma", b"audio", {"format": "transcribe"})
    assert a != make_key("timbre", b"audio", {"format": "verbatim"})


def test_key_ignores_settings_order() -> None:
    assert make_key("p", b"x", {"a": 1, "b": 2}) == make_key("p", b"x", {"b": 2, "a": 1})


def test_put_get_roundtrip(cache: Cache) -> None:
    key = make_key("prisma", b"x", {})
    assert cache.get(key) is None
    cache.put(key, "prisma", {}, "வணக்கம்".encode(), latency_ms=123.4)
    entry = cache.get(key)
    assert entry is not None
    assert entry.value.decode() == "வணக்கம்"
    assert entry.latency_ms == 123.4


def test_persists_across_instances(tmp_path) -> None:
    path = tmp_path / "sub" / "c.sqlite"
    c1 = Cache(path)
    key = make_key("timbre", b"text", {"voice": "Trisha"})
    c1.put(key, "timbre", {"voice": "Trisha"}, b"RIFF....", latency_ms=5.0)
    c1.close()
    c2 = Cache(path)
    assert c2.get(key) is not None
    assert c2.count("timbre") == 1 and c2.count("prisma") == 0
    c2.close()
