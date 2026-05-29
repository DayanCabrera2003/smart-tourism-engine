import pytest
from sqlalchemy import delete

from src.ingestion.store import destinations, engine


@pytest.fixture(autouse=True)
def _disable_web_fallback_by_default():
    """Desactiva la busqueda web (Tavily) por defecto en todos los tests.

    Los endpoints de busqueda inyectan ``get_web_client``; con una
    ``TAVILY_API_KEY`` presente en el entorno local, cualquier test que no la
    sobreescriba acabaria llamando a Tavily de verdad. Este fixture la fija en
    ``None`` por defecto. Los tests del fallback la sobreescriben de forma
    explicita con un cliente fake en su propio setup.
    """
    from src.api.main import app, get_web_client

    app.dependency_overrides[get_web_client] = lambda: None
    yield
    app.dependency_overrides.pop(get_web_client, None)


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
