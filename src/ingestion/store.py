"""
Persistencia de destinos turísticos en SQLite usando SQLAlchemy.
Incluye función upsert_destination().
"""
from typing import Optional
from sqlalchemy import create_engine, Column, String, Float, DateTime, Table, MetaData, select, insert, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import sessionmaker
import json
from datetime import datetime

from src.config import settings

# Derivar ruta desde settings para que DATA_DIR sea respetado
_db_path = settings.DATA_DIR / "processed" / "destinations.db"
_db_path.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{_db_path}"
engine = create_engine(DATABASE_URL, echo=False, future=True)
metadata = MetaData()

# Tabla destinations

destinations = Table(
    "destinations",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("country", String, nullable=False),
    Column("region", String),
    Column("description", String),
    Column("description_normalized", String),
    Column("tags", String),  # JSON-encoded list
    Column("image_urls", String),  # JSON-encoded list
    Column("lat", Float),
    Column("lon", Float),
    Column("source", String, nullable=False),
    Column("fetched_at", DateTime, nullable=False),
)

metadata.create_all(engine)
Session = sessionmaker(bind=engine, future=True)

def upsert_destination(dest) -> None:
    """
    Inserta o actualiza un destino en la tabla destinations.
    dest: instancia de Destination (Pydantic) o dict compatible.
    """
    values = {
        "id": dest.id,
        "name": dest.name,
        "country": dest.country,
        "region": dest.region,
        "description": dest.description,
        "description_normalized": getattr(dest, "description_normalized", None),
        "tags": json.dumps(dest.tags),
        "image_urls": json.dumps([str(u) for u in dest.image_urls]),
        "lat": dest.coordinates[0] if dest.coordinates else None,
        "lon": dest.coordinates[1] if dest.coordinates else None,
        "source": dest.source,
        "fetched_at": dest.fetched_at if isinstance(dest.fetched_at, datetime) else datetime.now(),
    }
    stmt = sqlite_insert(destinations).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[destinations.c.id],
        set_=values
    )
    with Session() as session:
        session.execute(stmt)
        session.commit()
