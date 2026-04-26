"""
Area tracking service: save, load, and manage tracked flood areas.
File-based storage at data/tracked_areas.jsonl
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

from backend.app.services.real_time_detection import compute_flood_assessment, FloodDetectionInput
from backend.app.services.data_sources import fetch_climate_baseline
from backend.app.services.notifications import send_high_risk_notification
from backend.app.models.schemas import ClimateBaselineRequest


DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TRACKED_AREAS_FILE = DATA_DIR / "tracked_areas.jsonl"


def _same_bbox(a: List[float], b: List[float], tol: float = 1e-6) -> bool:
    if len(a) != 4 or len(b) != 4:
        return False
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _ensure_data_dir():
    """Create data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _save_tracked_areas(areas: List[Dict[str, Any]]) -> None:
    """Rewrite the tracked areas file with the provided records."""
    _ensure_data_dir()
    with open(TRACKED_AREAS_FILE, "w") as f:
        for area in areas:
            f.write(json.dumps(area) + "\n")


def add_tracked_area(bbox: List[float], label: str = None) -> Dict[str, Any]:
    """
    Save a new tracked area to file.
    
    Args:
        bbox: [min_lon, min_lat, max_lon, max_lat]
        label: Optional name for the area
    
    Returns:
        Area record with ID and metadata
    """
    _ensure_data_dir()

    # Avoid duplicate tracked entries for the same bbox.
    existing_areas = load_tracked_areas()
    for existing in existing_areas:
        if _same_bbox(existing.get("bbox", []), bbox):
            return existing
    
    area_id = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    area_record = {
        "id": area_id,
        "bbox": bbox,
        "label": label or f"Area_{area_id}",
        "added_at": datetime.now(timezone.utc).isoformat(),
        "last_checked": None,
        "flood_status": None,
        "flood_score": None,
        "estimated_water_height_m": None,
        "confidence": None,
    }
    
    # Append to file (JSONL format)
    with open(TRACKED_AREAS_FILE, "a") as f:
        f.write(json.dumps(area_record) + "\n")
    
    return area_record


def load_tracked_areas() -> List[Dict[str, Any]]:
    """Load all tracked areas from file."""
    _ensure_data_dir()
    
    if not TRACKED_AREAS_FILE.exists():
        return []
    
    areas = []
    with open(TRACKED_AREAS_FILE, "r") as f:
        for line in f:
            if line.strip():
                areas.append(json.loads(line))
    
    return areas


def update_tracked_area(updated_area: Dict[str, Any]) -> Dict[str, Any]:
    """Update a tracked area by id and persist changes."""
    areas = load_tracked_areas()
    replaced = False

    for idx, area in enumerate(areas):
        if area.get("id") == updated_area.get("id"):
            areas[idx] = updated_area
            replaced = True
            break

    if not replaced:
        areas.append(updated_area)

    _save_tracked_areas(areas)
    return updated_area


def check_area_for_flood(area: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check a single area for flooding using real_time_detection.py
    
    Returns updated area record with flood_score and flood_status
    """
    bbox = area["bbox"]
    min_lon, min_lat, max_lon, max_lat = bbox
    lat = (min_lat + max_lat) / 2
    lon = (min_lon + max_lon) / 2
    
    # Retry windows to improve reliability when one short window has no valid pixels.
    end_time = datetime.now(timezone.utc)
    retry_windows_hours = [48, 96, 168]
    
    try:
        assessment = None
        used_window_hours = None

        for window_hours in retry_windows_hours:
            start_time = end_time - timedelta(hours=window_hours)

            # Fetch rainfall anomaly for the same analysis window.
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
                message = str(err)
                if "no valid VV pixels" in message.lower() or "no valid" in message.lower():
                    # Try a wider window before failing.
                    continue
                raise

        if assessment is None:
            raise ValueError("Sentinel Hub returned no valid VV pixels across retry windows (48h/96h/168h)")

        flood_score = assessment["flood_score"]
        
        # Determine status
        if flood_score > 0.7:
            flood_status = "HIGH"
        elif flood_score > 0.4:
            flood_status = "MEDIUM"
        else:
            flood_status = "LOW"
        
        area["flood_score"] = flood_score
        area["flood_status"] = flood_status
        area["estimated_water_height_m"] = assessment["estimated_water_height_m"]
        area["confidence"] = assessment["confidence"]
        area["analysis_window_hours"] = used_window_hours
        area["last_checked"] = datetime.now(timezone.utc).isoformat()
        area.pop("error", None)
        
        return area
    
    except Exception as e:
        area["flood_status"] = "ERROR"
        area["flood_score"] = None
        area["estimated_water_height_m"] = None
        area["confidence"] = None
        area["analysis_window_hours"] = None
        area["last_checked"] = datetime.now(timezone.utc).isoformat()
        area["error"] = str(e)
        return area


def check_all_areas() -> List[Dict[str, Any]]:
    """
    Check all tracked areas for flooding.
    This is called by the scheduler daily.
    
    Returns list of updated area records
    """
    areas = load_tracked_areas()
    updated_areas = []
    
    for area in areas:
        previous_status = area.get("flood_status")
        updated_area = check_area_for_flood(area)

        if previous_status != "HIGH" and updated_area.get("flood_status") == "HIGH":
            alert_sent = send_high_risk_notification(updated_area, previous_status)
            if alert_sent:
                updated_area["last_alert_sent_at"] = datetime.now(timezone.utc).isoformat()

        updated_areas.append(updated_area)
    
    # Rewrite file with updated records
    _save_tracked_areas(updated_areas)
    
    return updated_areas


def delete_tracked_area(area_id: int) -> bool:
    """Delete a tracked area by ID."""
    areas = load_tracked_areas()
    filtered_areas = [a for a in areas if a["id"] != area_id]
    
    if len(filtered_areas) == len(areas):
        return False  # Area not found
    
    _save_tracked_areas(filtered_areas)
    
    return True
