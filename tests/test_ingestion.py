from datetime import datetime

import pytest
from pydantic import ValidationError

from src.ingestion.models import Destination


def test_destination_creation_valid():
    """
    Verifica que se puede crear un objeto Destination con datos válidos.
    """
    data = {
        "id": "madrid-es",
        "name": "Madrid",
        "country": "España",
        "description": "Capital de España.",
        "source": "manual",
    }
    dest = Destination(**data)
    assert dest.id == "madrid-es"
    assert dest.name == "Madrid"
    assert dest.country == "España"
    assert dest.description == "Capital de España."
    assert dest.source == "manual"
    assert isinstance(dest.fetched_at, datetime)
    assert dest.tags == []
    assert dest.image_urls == []


def test_destination_creation_full():
    """
    Verifica la creación con todos los campos opcionales presentes.
    """
    data = {
        "id": "bcn-es",
        "name": "Barcelona",
        "country": "España",
        "region": "Cataluña",
        "description": "Ciudad cosmopolita.",
        "tags": ["playa", "gaudi"],
        "image_urls": ["https://example.com/bcn.jpg"],
        "coordinates": (41.385063, 2.173404),
        "source": "wikivoyage",
        "fetched_at": datetime(2026, 4, 7),
    }
    dest = Destination(**data)
    assert dest.region == "Cataluña"
    assert "playa" in dest.tags
    assert dest.image_urls[0] == "https://example.com/bcn.jpg"
    assert dest.coordinates == (41.385063, 2.173404)
    assert dest.fetched_at == datetime(2026, 4, 7)


def test_destination_missing_required():
    """
    Verifica que falla si faltan campos obligatorios.
    """
    with pytest.raises(ValidationError):
        Destination(id="test")  # Faltan name, country, etc.


def test_destination_invalid_types():
    """
    Verifica que falla con tipos de datos incorrectos.

    T126: image_urls ahora acepta paths locales además de URLs, así que
    validamos un tipo incorrecto en otro campo (coordinates espera
    tupla de dos floats).
    """
    with pytest.raises(ValidationError):
        Destination(
            id="test",
            name="Test",
            country="Test",
            description="Test",
            source="Test",
            coordinates="not-a-tuple",  # type: ignore[arg-type]
        )


def test_destination_accepts_local_image_paths():
    """T126: image_urls puede contener paths relativos del corpus local."""
    dest = Destination(
        id="madrid-es",
        name="Madrid",
        country="España",
        description="Capital.",
        source="manual",
        image_urls=["data/raw/images/madrid-es/wikipedia.jpg"],
    )
    assert dest.image_urls == ["data/raw/images/madrid-es/wikipedia.jpg"]
