from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from backend.app.services.real_time_detection import compute_flood_assessment, FloodDetectionInput
from backend.app.services.data_sources import fetch_climate_baseline
from backend.app.services.area_tracking import (
    add_tracked_area,
    check_all_areas,
    check_area_for_flood,
    delete_tracked_area,
    load_tracked_areas,
    update_tracked_area,
)
from backend.app.services.notifications import simulate_high_risk_notification
from backend.app.models.schemas import ClimateBaselineRequest

import numpy as np

from risk import (
    Client,
    catalog_url,
    training_bbox,
    sentinel_monthly_ndwi,
    make_flood_mask,
    load_dem_and_worldcover,
    align_training_layers,
    training_dataframe,
    train_rf,
    predict_risk,
)

router = APIRouter(prefix="/flood", tags=["flood"])

class FloodRequest(BaseModel):
    bbox: List[float]

class HeatmapRequest(BaseModel):
    bbox: List[float]
    include_grid: bool = False

_ML_STATE: Dict[str, Any] = {
    "model": None,
    "catalog": None,
    "is_trained": False,
}


@router.post("/detect")
def detect_flood(payload: FloodRequest):
    try:
        bbox = payload.bbox

        if len(bbox) != 4:
            raise HTTPException(status_code=400, detail="bbox must be [min_lon, min_lat, max_lon, max_lat]")

        min_lon, min_lat, max_lon, max_lat = bbox

        # centroid (for climate data)
        lat = (min_lat + max_lat) / 2
        lon = (min_lon + max_lon) / 2

        end_time = datetime.now(timezone.utc)
        retry_windows_hours = [48, 96, 168]
        climate = None
        assessment = None
        used_window_hours = None

        for window_hours in retry_windows_hours:
            start_time = end_time - timedelta(hours=window_hours)

            climate = fetch_climate_baseline(
                ClimateBaselineRequest(
                    latitude=lat,
                    longitude=lon,
                    start_datetime=start_time,
                    end_datetime=end_time,
                )
            )

            flood_input = FloodDetectionInput(
                bbox=bbox,
                rainfall_anomaly=climate.precipitation_anomaly,
                start_datetime=start_time,
                end_datetime=end_time,
            )

            try:
                assessment = compute_flood_assessment(flood_input)
                used_window_hours = window_hours
                break
            except ValueError as err:
                if "no valid" in str(err).lower():
                    continue
                raise

        if assessment is None or climate is None:
            raise ValueError("Sentinel Hub returned no valid VV pixels across retry windows (48h/96h/168h)")

        score = assessment["flood_score"]

        return {
            "bbox": bbox,
            "flood_score": score,
            "estimated_water_height_m": assessment["estimated_water_height_m"],
            "confidence": assessment["confidence"],
            "payout_triggered": score > 0.7,
            "confidence_window_hours": used_window_hours,
            "climate_signal": {
                "rainfall_anomaly": climate.precipitation_anomaly,
                "temperature_anomaly": climate.temperature_anomaly,
                "soil_moisture_anomaly": climate.soil_moisture_anomaly,
            },
            "sar_signal": {
                "pre_vv": assessment["pre_vv"],
                "post_vv": assessment["post_vv"],
                "pre_valid_ratio": assessment["pre_valid_ratio"],
                "post_valid_ratio": assessment["post_valid_ratio"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# AREA TRACKING ENDPOINTS
# ============================================

class TrackAreaRequest(BaseModel):
    bbox: List[float]
    label: str = None


class SimulateAlertRequest(BaseModel):
    label: str = "Hackathon Demo Area"
    bbox: List[float] = [21.0, 45.6, 21.68, 45.92]
    flood_score: float = 0.92
    estimated_water_height_m: float = 1.35
    confidence: float = 0.88
    previous_status: str = "MEDIUM"


class TrackedAreaResponse(BaseModel):
    id: int
    bbox: List[float]
    label: str
    added_at: str
    last_checked: Optional[str] = None
    flood_status: Optional[str] = None
    flood_score: Optional[float] = None
    estimated_water_height_m: Optional[float] = None
    confidence: Optional[float] = None


@router.post("/track-area", response_model=TrackedAreaResponse)
def track_area(payload: TrackAreaRequest) -> TrackedAreaResponse:
    """Add a new area to track for daily flood checks."""
    try:
        if not payload.bbox or len(payload.bbox) != 4:
            raise HTTPException(status_code=400, detail="bbox must be [min_lon, min_lat, max_lon, max_lat]")

        area = add_tracked_area(payload.bbox, payload.label)

        # Compute an initial status immediately so UI does not stay on "Checking...".
        checked_area = check_area_for_flood(area)
        update_tracked_area(checked_area)

        return TrackedAreaResponse(**checked_area)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Track area failed: {str(e)}")


@router.get("/tracked-areas", response_model=List[TrackedAreaResponse])
def get_tracked_areas() -> List[TrackedAreaResponse]:
    """Get all tracked areas with their current flood status."""
    try:
        areas = load_tracked_areas()
        return [TrackedAreaResponse(**a) for a in areas]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-areas")
def manual_check_all_areas() -> Dict[str, Any]:
    """Manually trigger flood check for all tracked areas (normally runs daily)."""
    try:
        updated_areas = check_all_areas()
        
        high_risk_count = sum(1 for a in updated_areas if a.get("flood_status") == "HIGH")
        medium_risk_count = sum(1 for a in updated_areas if a.get("flood_status") == "MEDIUM")
        
        return {
            "total_areas": len(updated_areas),
            "high_risk": high_risk_count,
            "medium_risk": medium_risk_count,
            "areas": [TrackedAreaResponse(**a) for a in updated_areas],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate-alert")
def simulate_alert(payload: SimulateAlertRequest) -> Dict[str, Any]:
    """
    Hackathon endpoint: simulate a HIGH-risk transition alert instantly.
    """
    try:
        if len(payload.bbox) != 4:
            raise HTTPException(status_code=400, detail="bbox must be [min_lon, min_lat, max_lon, max_lat]")

        area = {
            "id": f"demo-{int(datetime.now(timezone.utc).timestamp())}",
            "label": payload.label,
            "bbox": payload.bbox,
            "flood_status": "HIGH",
            "flood_score": payload.flood_score,
            "estimated_water_height_m": payload.estimated_water_height_m,
            "confidence": payload.confidence,
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }

        result = simulate_high_risk_notification(area, previous_status=payload.previous_status)
        return {
            "message": "Simulated HIGH-risk alert triggered",
            "area": area,
            "notification": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tracked-area/{area_id}")
def remove_tracked_area(area_id: int) -> Dict[str, str]:
    """Delete a tracked area by ID."""
    try:
        success = delete_tracked_area(area_id)
        if not success:
            raise HTTPException(status_code=404, detail="Area not found")
        return {"message": "Area removed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

# ============================================
# RISK HEATMAP
# ============================================

def _ensure_ml_model() -> str:
    if _ML_STATE["is_trained"]:
        return "ready"
    
    catalog = Client.open(catalog_url)

    ndwi_may_2023 = sentinel_monthly_ndwi(catalog, training_bbox, "2023-05-01/2023-05-31")
    ndwi_may_2024 = sentinel_monthly_ndwi(catalog, training_bbox, "2024-05-01/2024-05-31")
    flood_mask = make_flood_mask(ndwi_may_2023, ndwi_may_2024)

    dem, wc = load_dem_and_worldcover(catalog, training_bbox)
    elevation, slope, landcover, _building_flag, permanent_water_mask, dist_to_water = align_training_layers(
        dem, wc, ndwi_may_2023
    )

    df = training_dataframe(
        elevation, slope, landcover, flood_mask, dist_to_water, permanent_water_mask
    )
    model = train_rf(df)

    _ML_STATE["catalog"] = catalog
    _ML_STATE["model"] = model
    _ML_STATE["is_trained"] = True
    return "trained_now"

@router.post("/heatmap")
def heatmap(payload: HeatmapRequest) -> Dict[str, Any]:
    try:
        bbox = payload.bbox
        if len(bbox) != 4:
            raise HTTPException(status_code=400, detail="bbox must be [min_lon, min_lat, max_lon, max_lat]")

        status = _ensure_ml_model()

        risk_da = predict_risk(bbox, _ML_STATE["model"], _ML_STATE["catalog"])
        arr = risk_da.values.astype("float32")
        valid = np.isfinite(arr)

        response: Dict[str, Any] = {
            "bbox": bbox,
            "model_status": status,
            "width": int(arr.shape[1]),
            "height": int(arr.shape[0]),
            "min_risk": float(np.nanmin(arr)) if valid.any() else None,
            "max_risk": float(np.nanmax(arr)) if valid.any() else None,
            "mean_risk": float(np.nanmean(arr)) if valid.any() else None,
            "nodata_value": -1.0,
        }

        if payload.include_grid:
            response["risk_grid"] = np.where(np.isfinite(arr), arr, -1.0).tolist()
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

