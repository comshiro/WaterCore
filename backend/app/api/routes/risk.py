import httpx
from fastapi import APIRouter, HTTPException, Query

from backend.app.core.config import get_settings
from backend.app.models.schemas import (
    ClimateBaselineRequest,
    ClimateBaselineResponse,
    DerivedLayerRequest,
    DerivedLayerResponse,
    RiskInput,
    RiskResponse,
    SceneSearchRequest,
    SceneSearchResponse,
)
from backend.app.services.data_sources import (
    fetch_climate_baseline,
    get_demo_copernicus_signals,
    get_sentinel_hub_derived_layer,
    search_copernicus_scenes,
)
from backend.app.services.risk_engine import compute_risk

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/score", response_model=RiskResponse)
def score_risk(payload: RiskInput, threshold: float | None = Query(default=None, ge=0, le=1)) -> RiskResponse:
    settings = get_settings()
    active_threshold = threshold if threshold is not None else settings.default_alert_threshold
    return compute_risk(payload, active_threshold)


@router.get("/demo", response_model=RiskResponse)
def demo_risk(threshold: float | None = Query(default=None, ge=0, le=1)) -> RiskResponse:
    settings = get_settings()
    active_threshold = threshold if threshold is not None else settings.default_alert_threshold
    signals = get_demo_copernicus_signals()
    payload = RiskInput(latitude=45.757, longitude=21.23, **signals)
    return compute_risk(payload, active_threshold)


@router.post("/scenes", response_model=SceneSearchResponse)
def scene_discovery(payload: SceneSearchRequest) -> SceneSearchResponse:
    try:
        return search_copernicus_scenes(payload)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Copernicus STAC request failed: {exc.response.text}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Cannot reach Copernicus STAC: {exc}") from exc


@router.post("/derived-layer", response_model=DerivedLayerResponse)
def derived_layer(payload: DerivedLayerRequest) -> DerivedLayerResponse:
    try:
        return get_sentinel_hub_derived_layer(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Sentinel Hub process request failed: {exc.response.text}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Cannot reach Sentinel Hub: {exc}") from exc


@router.post("/climate-baseline", response_model=ClimateBaselineResponse)
def climate_baseline(payload: ClimateBaselineRequest) -> ClimateBaselineResponse:
    """
    Fetch climate baseline anomalies (precipitation, temperature, soil moisture)
    for a given location and date range from CDS/ERA5.
    Falls back to synthetic data if CDS API is unavailable.
    """
    try:
        return fetch_climate_baseline(payload)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"CDS request failed: {exc.response.text}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Cannot reach CDS/ERA5: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Climate baseline fetch error: {str(exc)}") from exc