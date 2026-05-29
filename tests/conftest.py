"""Configuracion compartida de tests.

Aisla la sesion de pytest del estado real del demo:

- Redirige el engine SQLite del catalogo (``src.ingestion.store``) a una BD
  temporal de sesion. Sin esto, fixtures como ``clean_db`` (delete masivo) y
  cualquier ``upsert_destination`` en tests escriben sobre
  ``data/processed/destinations.db`` — la misma BD que el contenedor del demo
  monta por bind-mount —, dejando el corpus vacio tras correr ``pytest``.
- Desactiva el cliente web (Tavily) por defecto en todos los tests para
  evitar que una ``TAVILY_API_KEY`` en el entorno local dispare llamadas
  reales cuando un test no la sobreescribe.
"""
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

import src.ingestion.store as _store_module

# Crear la BD temporal por sesion ANTES de que cualquier test (o codigo de
# src que el test importe) abra el engine real. ``src.ingestion.store`` ya
# corrio su modulo y dejo ``engine`` apuntando a la BD real; lo sustituimos
# en vivo y volvemos a crear el schema en la BD de tests para que
# ``Session()`` y las queries posteriores la usen.
_test_db_dir = Path(tempfile.mkdtemp(prefix="ste_test_db_"))
_test_db_path = _test_db_dir / "destinations.db"
_test_engine = create_engine(f"sqlite:///{_test_db_path}", echo=False, future=True)
_store_module.metadata.create_all(_test_engine)
_store_module.engine = _test_engine
_store_module.Session = sessionmaker(bind=_test_engine, future=True)

# Re-importar referencias atadas al engine ya sustituido. Cualquier consumidor
# que haga ``from src.ingestion.store import engine`` despues de este punto
# obtiene el engine de tests.
from src.ingestion.store import destinations, engine  # noqa: E402


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
    """Limpia la tabla destinations antes y después de cada test.

    Opera sobre la BD temporal de la sesion (parchada arriba), nunca sobre la
    SQLite real del demo.
    """
    with engine.connect() as conn:
        conn.execute(delete(destinations))
        conn.commit()
    yield
    with engine.connect() as conn:
        conn.execute(delete(destinations))
        conn.commit()
