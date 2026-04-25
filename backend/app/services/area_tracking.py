"""
Area tracking service: save, load, and manage tracked flood areas.
File-based storage at data/tracked_areas.jsonl
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

from backend.app.services.real_time_detection import compute_flood_score, FloodDetectionInput
from backend.app.services.data_sources import fetch_climate_baseline
from backend.app.models.schemas import ClimateBaselineRequest


DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TRACKED_AREAS_FILE = DATA_DIR / "tracked_areas.jsonl"


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
    
    area_id = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    area_record = {
        "id": area_id,
        "bbox": bbox,
        "label": label or f"Area_{area_id}",
        "added_at": datetime.now(timezone.utc).isoformat(),
        "last_checked": None,
        "flood_status": None,
        "flood_score": None,
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
    
    # 48h window for Sentinel-1 analysis
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=48)
    
    try:
        # Fetch rainfall anomaly
        climate = fetch_climate_baseline(
            ClimateBaselineRequest(
                latitude=lat,
                longitude=lon,
                start_datetime=start_time,
                end_datetime=end_time,
            )
        )
        
        # Compute flood score
        flood_input = FloodDetectionInput(
            bbox=bbox,
            rainfall_anomaly=climate.precipitation_anomaly,
            start_datetime=start_time,
            end_datetime=end_time,
        )
        
        flood_score = compute_flood_score(flood_input)
        
        # Determine status
        if flood_score > 0.7:
            flood_status = "HIGH"
        elif flood_score > 0.4:
            flood_status = "MEDIUM"
        else:
            flood_status = "LOW"
        
        area["flood_score"] = flood_score
        area["flood_status"] = flood_status
        area["last_checked"] = datetime.now(timezone.utc).isoformat()
        area.pop("error", None)
        
        return area
    
    except Exception as e:
        area["flood_status"] = "ERROR"
        area["flood_score"] = None
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
        updated_area = check_area_for_flood(area)
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
