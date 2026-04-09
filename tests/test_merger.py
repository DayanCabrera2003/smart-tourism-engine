from datetime import datetime

from src.ingestion.merger import merge_destinations
from src.ingestion.models import Destination


def make_dest(
    id, name, lat, lon, source, tags=None, image_urls=None, region=None, description=None
):
    return Destination(
        id=id,
        name=name,
        country="España",
        region=region,
        description=description or "desc",
        source=source,
        coordinates=(lat, lon),
        tags=tags or [],
        image_urls=image_urls or [],
        fetched_at=datetime.now(),
    )

def test_merge_destinations_dedup():
    d1 = make_dest(
        "1", "Madrid", 40.4168, -3.7038, "wikivoyage",
        tags=["ciudad"], image_urls=["http://img1.com"],
        region="Comunidad de Madrid", description="Capital de España",
    )
    d2 = make_dest("2", "Madrid ", 40.41681, -3.70381, "opentripmap", tags=["capital"], image_urls=["http://img2.com"])
    d3 = make_dest("3", "Barcelona", 41.3879, 2.16992, "wikivoyage")
    merged = merge_destinations([[d1], [d2], [d3]])
    names = sorted([d.name.strip().lower() for d in merged])
    assert "madrid" in names
    assert "barcelona" in names
    assert len(merged) == 2
    madrid = next(d for d in merged if d.name.strip().lower() == "madrid")
    # Tags y urls fusionados
    assert set(madrid.tags) == {"ciudad", "capital"}
    assert set(str(url) for url in madrid.image_urls) == {"http://img1.com/", "http://img2.com/"}
    # Región y descripción se conservan si existen
    assert madrid.region == "Comunidad de Madrid"
    assert madrid.description == "Capital de España"
