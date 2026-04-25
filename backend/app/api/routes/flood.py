from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from backend.app.services.real_time_detection import compute_flood_score, FloodDetectionInput
from backend.app.services.data_sources import fetch_climate_baseline
from backend.app.services.area_tracking import (
    add_tracked_area,
    check_all_areas,
    check_area_for_flood,
    delete_tracked_area,
    load_tracked_areas,
    update_tracked_area,
)
from backend.app.models.schemas import ClimateBaselineRequest

router = APIRouter(prefix="/flood", tags=["flood"])

class FloodRequest(BaseModel):
    bbox: List[float]


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

        # 48h window assumption (insurance logic)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=48)

        # fetch rainfall anomaly (REAL CDS pipeline via your service)
        climate = fetch_climate_baseline(
            ClimateBaselineRequest(
                latitude=lat,
                longitude=lon,
                start_datetime=start_time,
                end_datetime=end_time,
            )
        )

        # build proper input
        flood_input = FloodDetectionInput(
            bbox=bbox,
            rainfall_anomaly=climate.precipitation_anomaly,
            start_datetime=start_time,
            end_datetime=end_time,
        )

        score = compute_flood_score(flood_input)

        return {
            "bbox": bbox,
            "flood_score": score,
            "payout_triggered": score > 0.7,
            "confidence_window_hours": 48,
            "climate_signal": {
                "rainfall_anomaly": climate.precipitation_anomaly,
                "temperature_anomaly": climate.temperature_anomaly,
                "soil_moisture_anomaly": climate.soil_moisture_anomaly,
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


class TrackedAreaResponse(BaseModel):
    id: int
    bbox: List[float]
    label: str
    added_at: str
    last_checked: Optional[str] = None
    flood_status: Optional[str] = None
    flood_score: Optional[float] = None


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