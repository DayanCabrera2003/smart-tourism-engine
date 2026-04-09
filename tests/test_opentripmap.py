
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import Request, Response

from src.ingestion.opentripmap import OpenTripMapClient


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

    def bbox_callback(request: Request):
        # The base_url is set on the httpx.AsyncClient,
        # so request.url.path will be just the endpoint
        assert request.url.path == "/0.1/en/places/bbox"
        assert request.url.params["apikey"] == "test_api_key"
        assert request.url.params["lon_min"] == "-3.71"
        assert request.url.params["lat_min"] == "40.4"
        assert request.url.params["lon_max"] == "-3.67"
        assert request.url.params["lat_max"] == "40.43"
        assert request.url.params["limit"] == "50"
        return Response(200, json=bbox_response, request=request)

    httpx_mock.add_callback(bbox_callback)

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

    def bbox_kinds_callback(request: Request):
        assert request.url.path == "/0.1/en/places/bbox"
        assert request.url.params["apikey"] == "test_api_key"
        assert request.url.params["lon_min"] == "-3.71"
        assert request.url.params["lat_min"] == "40.4"
        assert request.url.params["lon_max"] == "-3.67"
        assert request.url.params["lat_max"] == "40.43"
        assert request.url.params["limit"] == "50"
        assert request.url.params["kinds"] == "museums"
        return Response(200, json=bbox_response, request=request)

    httpx_mock.add_callback(bbox_kinds_callback)

    client = OpenTripMapClient(api_key="test_api_key")
    pois = await client.get_pois_in_bbox(
        lon_min=-3.71, lat_min=40.40, lon_max=-3.67, lat_max=40.43, kinds="museums"
    )

    assert len(pois) == 1
    assert pois[0]["properties"]["name"] == "Museum"

@pytest.mark.asyncio
async def test_get_pois_in_bbox_http_error(httpx_mock):
    """Verifica el manejo de errores HTTP para get_pois_in_bbox."""

    def bbox_http_error_callback(request: Request):
        assert request.url.path == "/0.1/en/places/bbox"
        assert request.url.params["apikey"] == "test_api_key"
        return Response(403, request=request)

    httpx_mock.add_callback(bbox_http_error_callback)

    client = OpenTripMapClient(api_key="test_api_key")
    pois = await client.get_pois_in_bbox(lon_min=-3.71, lat_min=40.40, lon_max=-3.67, lat_max=40.43)

    assert pois == []

@pytest.mark.asyncio
async def test_get_pois_in_bbox_network_error(httpx_mock):
    """Verifica el manejo de errores de red para get_pois_in_bbox."""
    # is_reusable=True para cubrir los MAX_RETRIES reintentos; sleep mockeado para rapidez
    httpx_mock.add_exception(httpx.RequestError("Network error"), is_reusable=True)

    with patch("src.ingestion.opentripmap.asyncio.sleep", new_callable=AsyncMock):
        client = OpenTripMapClient(api_key="test_api_key")
        pois = await client.get_pois_in_bbox(
            lon_min=-3.71, lat_min=40.40, lon_max=-3.67, lat_max=40.43
        )

    assert pois == []

@pytest.mark.asyncio
async def test_get_poi_details_success(httpx_mock):
    """Verifica que get_poi_details devuelva detalles correctamente."""
    poi_details_response = {
        "xid": "Q1",
        "name": "Detailed POI 1",
        "description": "Some description"
    }
    
    def details_callback(request: Request):
        assert request.url.path == "/0.1/en/places/xid/Q1"
        assert request.url.params["apikey"] == "test_api_key"
        return Response(200, json=poi_details_response, request=request)

    httpx_mock.add_callback(details_callback)

    client = OpenTripMapClient(api_key="test_api_key")
    details = await client.get_poi_details("Q1")

    assert details is not None
    assert details["name"] == "Detailed POI 1"

@pytest.mark.asyncio
async def test_get_poi_details_http_error(httpx_mock):
    """Verifica el manejo de errores HTTP para get_poi_details."""

    def details_http_error_callback(request: Request):
        assert request.url.path == "/0.1/en/places/xid/Q1"
        assert request.url.params["apikey"] == "test_api_key"
        return Response(404, request=request)

    httpx_mock.add_callback(details_http_error_callback)

    client = OpenTripMapClient(api_key="test_api_key")
    details = await client.get_poi_details("Q1")

    assert details is None

@pytest.mark.asyncio
async def test_get_poi_details_network_error(httpx_mock):
    """Verifica el manejo de errores de red para get_poi_details."""
    # is_reusable=True para cubrir los MAX_RETRIES reintentos; sleep mockeado para rapidez
    httpx_mock.add_exception(httpx.RequestError("Network error"), is_reusable=True)

    with patch("src.ingestion.opentripmap.asyncio.sleep", new_callable=AsyncMock):
        client = OpenTripMapClient(api_key="test_api_key")
        details = await client.get_poi_details("Q1")

    assert details is None
