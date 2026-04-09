import pytest
from sqlalchemy import delete
from src.ingestion.store import engine, destinations


@pytest.fixture
def sample_destination_data():
    return {
        "id": "test-dest",
        "name": "Test",
        "country": "Spain",
        "description": "Test description",
        "source": "test",
    }


@pytest.fixture
def clean_db():
    """Limpia la tabla destinations antes y después de cada test."""
    with engine.connect() as conn:
        conn.execute(delete(destinations))
        conn.commit()
    yield
    with engine.connect() as conn:
        conn.execute(delete(destinations))
        conn.commit()
