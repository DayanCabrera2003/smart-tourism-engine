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
    assert str(dest.image_urls[0]) == "https://example.com/bcn.jpg"
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
    """
    with pytest.raises(ValidationError):
        Destination(
            id="test",
            name="Test",
            country="Test",
            description="Test",
            source="Test",
            image_urls=["no-es-una-url"],
        )
