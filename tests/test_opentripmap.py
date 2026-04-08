import pytest
import httpx
from httpx import Response, Request
from src.ingestion.opentripmap import OpenTripMapClient
from src.config import Settings

@pytest.fixture
def mock_settings():
    """Fixture para mockear las configuraciones con una API key de prueba."""
    original_settings = Settings()
    original_settings.OPENTRIPMAP_API_KEY = "test_api_key"
    return original_settings

@pytest.fixture
def opentripmap_client(mock_settings):
    """Fixture que proporciona una instancia de OpenTripMapClient con una API key mockeada."""
    return OpenTripMapClient(api_key=mock_settings.OPENTRIPMAP_API_KEY)

@pytest.mark.asyncio
async def test_client_initialization_no_api_key():
    """Verifica que el cliente no se inicialice sin API key."""
    with pytest.raises(ValueError, match="OpenTripMap API key is required."):
        OpenTripMapClient(api_key="")

@pytest.mark.asyncio
async def test_get_pois_in_bbox_success(httpx_mock):
    """Verifica que get_pois_in_bbox devuelva POIs correctamente."""
    bbox_response = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": "1", "properties": {"xid": "Q1", "name": "POI 1"}},
            {"type": "Feature", "id": "2", "properties": {"xid": "Q2", "name": "POI 2"}},
        ],
    }
    httpx_mock.add_response(
        url="https://api.opentripmap.com/0.1/en/places/bbox?apikey=test_api_key&lon_min=-3.71&lat_min=40.40&lon_max=-3.67&lat_max=40.43&limit=50",
        json=bbox_response,
    )

    client = OpenTripMapClient(api_key="test_api_key")
    pois = await client.get_pois_in_bbox(lon_min=-3.71, lat_min=40.40, lon_max=-3.67, lat_max=40.43)

    assert len(pois) == 2
    assert pois[0]["properties"]["name"] == "POI 1"
    assert pois[1]["properties"]["name"] == "POI 2"

@pytest.mark.asyncio
async def test_get_pois_in_bbox_with_kinds(httpx_mock):
    """Verifica que get_pois_in_bbox funcione con el parámetro 'kinds'."""
    bbox_response = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": "3", "properties": {"xid": "Q3", "name": "Museum"}},
        ],
    }
    httpx_mock.add_response(
        url="https://api.opentripmap.com/0.1/en/places/bbox?apikey=test_api_key&lon_min=-3.71&lat_min=40.40&lon_max=-3.67&lat_max=40.43&limit=50&kinds=museums",
        json=bbox_response,
    )

    client = OpenTripMapClient(api_key="test_api_key")
    pois = await client.get_pois_in_bbox(lon_min=-3.71, lat_min=40.40, lon_max=-3.67, lat_max=40.43, kinds="museums")

    assert len(pois) == 1
    assert pois[0]["properties"]["name"] == "Museum"

@pytest.mark.asyncio
async def test_get_pois_in_bbox_http_error(httpx_mock):
    """Verifica el manejo de errores HTTP para get_pois_in_bbox."""
    httpx_mock.add_response(
        url="https://api.opentripmap.com/0.1/en/places/bbox?apikey=test_api_key&lon_min=-3.71&lat_min=40.40&lon_max=-3.67&lat_max=40.43&limit=50",
        status_code=403,
    )

    client = OpenTripMapClient(api_key="test_api_key")
    pois = await client.get_pois_in_bbox(lon_min=-3.71, lat_min=40.40, lon_max=-3.67, lat_max=40.43)

    assert pois == []

@pytest.mark.asyncio
async def test_get_pois_in_bbox_network_error(httpx_mock):
    """Verifica el manejo de errores de red para get_pois_in_bbox."""
    httpx_mock.add_exception(httpx.RequestError("Network error"), url="https://api.opentripmap.com/0.1/en/places/bbox")

    client = OpenTripMapClient(api_key="test_api_key")
    pois = await client.get_pois_in_bbox(lon_min=-3.71, lat_min=40.40, lon_max=-3.67, lat_max=40.43)

    assert pois == []

@pytest.mark.asyncio
async def test_get_poi_details_success(httpx_mock):
    """Verifica que get_poi_details devuelva detalles correctamente."""
    poi_details_response = {"xid": "Q1", "name": "Detailed POI 1", "description": "Some description"}
    httpx_mock.add_response(
        url="https://api.opentripmap.com/0.1/en/places/xid/Q1?apikey=test_api_key",
        json=poi_details_response,
    )

    client = OpenTripMapClient(api_key="test_api_key")
    details = await client.get_poi_details("Q1")

    assert details is not None
    assert details["name"] == "Detailed POI 1"

@pytest.mark.asyncio
async def test_get_poi_details_http_error(httpx_mock):
    """Verifica el manejo de errores HTTP para get_poi_details."""
    httpx_mock.add_response(
        url="https://api.opentripmap.com/0.1/en/places/xid/Q1?apikey=test_api_key",
        status_code=404,
    )

    client = OpenTripMapClient(api_key="test_api_key")
    details = await client.get_poi_details("Q1")

    assert details is None

@pytest.mark.asyncio
async def test_get_poi_details_network_error(httpx_mock):
    """Verifica el manejo de errores de red para get_poi_details."""
    httpx_mock.add_exception(httpx.RequestError("Network error"), url="https://api.opentripmap.com/0.1/en/places/xid/Q1")

    client = OpenTripMapClient(api_key="test_api_key")
    details = await client.get_poi_details("Q1")

    assert details is None
