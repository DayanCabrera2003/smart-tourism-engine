import pytest
from src.ingestion.models import Destination
from src.ingestion.store import upsert_destination, engine, destinations
from sqlalchemy import select
from datetime import datetime

@pytest.mark.usefixtures("clean_db")
def test_upsert_destination(tmp_path, monkeypatch):
    # Crear un destino
    dest = Destination(
        id="test1",
        name="Test City",
        country="Testland",
        region="Test Region",
        description="Una ciudad de prueba",
        description_normalized="una ciudad de prueba",
        tags=["ciudad", "prueba"],
        image_urls=["http://img.com/1.jpg"],
        coordinates=(10.0, 20.0),
        source="wikivoyage",
        fetched_at=datetime.now(),
    )
    upsert_destination(dest)
    # Verificar que está en la BD
    with engine.connect() as conn:
        row = conn.execute(select(destinations).where(destinations.c.id == "test1")).first()
        assert row is not None
        assert row.name == "Test City"
        assert row.country == "Testland"
        assert row.region == "Test Region"
        assert "ciudad" in row.tags
        assert "1.jpg" in row.image_urls
        assert abs(row.lat - 10.0) < 1e-6
        assert abs(row.lon - 20.0) < 1e-6
        assert row.source == "wikivoyage"
