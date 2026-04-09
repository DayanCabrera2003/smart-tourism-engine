from pathlib import Path

import pytest

from src.ingestion.images import download_images_for_destination
from src.ingestion.models import Destination


@pytest.mark.asyncio
async def test_download_images_for_destination(monkeypatch, tmp_path):
    # Simula descarga exitosa y fallida
    class DummyResp:
        def __init__(self, content, status=200):
            self.content = content
            self.status_code = status
        def raise_for_status(self):
            if self.status_code != 200:
                raise Exception("HTTP error")
    async def dummy_get(url):
        if "ok.jpg" in url:
            return DummyResp(b"1234")
        if "big.jpg" in url:
            return DummyResp(b"x" * (2*1024*1024+1))
        return DummyResp(b"", status=404)
    # Parchea httpx.AsyncClient.get
    import src.ingestion.images as images_mod
    class DummyHead:
        def __init__(self, content_length):
            self.headers = {"content-length": str(content_length)}
    class DummyClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def head(self, url):
            # Devuelve content-length 0 para que el chequeo recaiga en el GET real
            return DummyHead(0)
        async def get(self, url): return await dummy_get(url)
    monkeypatch.setattr(images_mod.httpx, "AsyncClient", lambda **_: DummyClient())
    from datetime import datetime
    dest = Destination(
        id="test1",
        name="Test",
        country="ES",
        description="desc",
        source="wikivoyage",
        coordinates=(0,0),
        tags=[],
        image_urls=["http://x.com/ok.jpg", "http://x.com/big.jpg", "http://x.com/fail.gif"],
        fetched_at=datetime.now(),
    )
    out = await download_images_for_destination(dest, base_folder=tmp_path)
    # Solo descarga la imagen válida y pequeña
    assert len(out) == 1
    assert out[0].endswith("ok.jpg")
    assert Path(out[0]).exists()
