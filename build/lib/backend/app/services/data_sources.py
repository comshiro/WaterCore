import base64
from datetime import datetime, timezone
from typing import Dict, List

import httpx

from backend.app.core.config import get_settings
from backend.app.models.schemas import (
    DerivedLayerRequest,
    DerivedLayerResponse,
    SceneItem,
    SceneSearchRequest,
    SceneSearchResponse,
)


def get_demo_copernicus_signals() -> Dict[str, float]:
    # Placeholder values for offline demos when APIs are not connected yet.
    return {
        "rainfall_anomaly": 1.8,
        "soil_moisture_anomaly": 2.1,
        "flood_signal": 0.62,
        "vegetation_stress": 0.44,
    }


def _to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def search_copernicus_scenes(payload: SceneSearchRequest) -> SceneSearchResponse:
    settings = get_settings()
    search_url = f"{settings.copernicus_stac_url.rstrip('/')}/search"

    request_body: Dict[str, object] = {
        "collections": [payload.collection],
        "bbox": payload.bbox,
        "datetime": f"{_to_utc_iso(payload.start_datetime)}/{_to_utc_iso(payload.end_datetime)}",
        "limit": payload.limit,
    }

    if payload.cloud_cover_lte is not None:
        request_body["query"] = {"eo:cloud_cover": {"lte": payload.cloud_cover_lte}}

    headers = {"Content-Type": "application/json"}
    if settings.copernicus_stac_token:
        headers["Authorization"] = f"Bearer {settings.copernicus_stac_token}"

    with httpx.Client(timeout=settings.copernicus_stac_timeout_seconds) as client:
        response = client.post(search_url, json=request_body, headers=headers)
        response.raise_for_status()
        raw = response.json()

    scenes: List[SceneItem] = []
    for item in raw.get("features", []):
        props = item.get("properties", {})
        scenes.append(
            SceneItem(
                scene_id=item.get("id", "unknown"),
                collection=item.get("collection"),
                acquisition_datetime=props.get("datetime"),
                bbox=item.get("bbox"),
                cloud_cover=props.get("eo:cloud_cover"),
            )
        )

    return SceneSearchResponse(
        source=settings.copernicus_stac_url,
        count=len(scenes),
        scenes=scenes,
    )


def _sentinel_hub_evalscript(layer_type: str) -> str:
    if layer_type == "ndwi":
        return """
//VERSION=3
function setup() {
  return {
    input: ["B03", "B08", "dataMask"],
    output: { bands: 4 }
  };
}

function evaluatePixel(sample) {
  let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08 + 1e-6);
  let normalized = (ndwi + 1.0) / 2.0;
  return [normalized, normalized, normalized, sample.dataMask];
}
""".strip()

    if layer_type == "ndvi":
        return """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "dataMask"],
    output: { bands: 4 }
  };
}

function evaluatePixel(sample) {
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04 + 1e-6);
  let normalized = (ndvi + 1.0) / 2.0;
  return [normalized, normalized, normalized, sample.dataMask];
}
""".strip()

    if layer_type == "flood_proxy_s1":
        return """
//VERSION=3
function setup() {
  return {
    input: ["VV", "VH", "dataMask"],
    output: { bands: 4 }
  };
}

function evaluatePixel(sample) {
  // Rough proxy: lower VV backscatter may correlate with open water.
  let vv = Math.max(sample.VV, 1e-6);
  let waterProxy = vv < 0.03 ? 1.0 : 0.0;
  return [waterProxy, waterProxy, waterProxy, sample.dataMask];
}
""".strip()

    raise ValueError("Unsupported layer_type. Use ndwi, ndvi, or flood_proxy_s1.")


def _sentinel_hub_access_token() -> str:
    settings = get_settings()
    if not settings.sentinel_hub_client_id or not settings.sentinel_hub_client_secret:
        raise ValueError("Sentinel Hub credentials are missing. Set SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET.")

    form_data = {
        "grant_type": "client_credentials",
        "client_id": settings.sentinel_hub_client_id,
        "client_secret": settings.sentinel_hub_client_secret,
    }

    with httpx.Client(timeout=settings.sentinel_hub_timeout_seconds) as client:
        token_response = client.post(settings.sentinel_hub_token_url, data=form_data)
        token_response.raise_for_status()
        token_payload = token_response.json()

    token = token_payload.get("access_token")
    if not token:
        raise ValueError("Sentinel Hub token response did not include access_token.")
    return token


def get_sentinel_hub_derived_layer(payload: DerivedLayerRequest) -> DerivedLayerResponse:
    settings = get_settings()
    token = _sentinel_hub_access_token()

    process_url = f"{settings.sentinel_hub_base_url.rstrip('/')}{settings.sentinel_hub_process_path}"
    request_body: Dict[str, object] = {
        "input": {
            "bounds": {
                "bbox": payload.bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [
                {
                    "type": payload.data_collection,
                    "dataFilter": {
                        "timeRange": {
                            "from": _to_utc_iso(payload.start_datetime),
                            "to": _to_utc_iso(payload.end_datetime),
                        }
                    },
                }
            ],
        },
        "output": {
            "width": payload.width,
            "height": payload.height,
            "responses": [{"identifier": "default", "format": {"type": payload.output_mime}}],
        },
        "evalscript": _sentinel_hub_evalscript(payload.layer_type),
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=settings.sentinel_hub_timeout_seconds) as client:
        response = client.post(process_url, json=request_body, headers=headers)
        response.raise_for_status()
        image_b64 = base64.b64encode(response.content).decode("utf-8")

    return DerivedLayerResponse(
        source=settings.sentinel_hub_base_url,
        layer_type=payload.layer_type,
        data_collection=payload.data_collection,
        mime_type=payload.output_mime,
        image_base64=image_b64,
    )
