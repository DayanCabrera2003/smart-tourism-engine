from src.ingestion.robots import RobotsCache


def test_is_allowed_permissive(monkeypatch):
    # Simula robots.txt permisivo
    class DummyParser:
        def can_fetch(self, ua, url):
            return True
    cache = RobotsCache()
    monkeypatch.setitem(cache.parsers, "example.com", DummyParser())
    assert cache.is_allowed("https://example.com/foo")

def test_is_allowed_blocked(monkeypatch):
    # Simula robots.txt restrictivo
    class DummyParser:
        def can_fetch(self, ua, url):
            return False
    cache = RobotsCache()
    monkeypatch.setitem(cache.parsers, "example.com", DummyParser())
    assert not cache.is_allowed("https://example.com/bar")
