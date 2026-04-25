from dataclasses import dataclass
from typing import List
from datetime import datetime

from backend.app.services.data_sources import get_sentinel1_vv_mean


# ----------------------------
# INPUT
# ----------------------------

@dataclass
class FloodDetectionInput:
    bbox: List[float]
    rainfall_anomaly: float  # 0–3 (ERA5/CDS)

    # optional future extension
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None


# ----------------------------
# SENTINEL SCENE (derived, NOT mocked)
# ----------------------------

@dataclass
class SentinelScene:
    scene_id: str
    acquisition_datetime: datetime
    bbox: List[float]
    vv_mean: float


# ----------------------------
# HELPERS
# ----------------------------

def _clamp(x: float, min_v: float = 0.0, max_v: float = 1.0) -> float:
    return max(min_v, min(max_v, x))


def compute_intensity(pre_vv: float, post_vv: float) -> float:
    return abs(pre_vv - post_vv)


def compute_flood_extent(pre_vv: float, post_vv: float) -> float:
    """
    SAR flood proxy:
    stronger VV drop → more flooding
    """
    delta = pre_vv - post_vv
    return _clamp(delta * 5.0)


def normalize_rainfall(rainfall_anomaly: float) -> float:
    return _clamp(rainfall_anomaly / 3.0)


# ----------------------------
# REAL SENTINEL-1 PIPELINE
# ----------------------------

def fetch_sentinel1_vv_pair(
    bbox: List[float],
    start: datetime,
    end: datetime
) -> tuple[float, float]:
    """
    REAL data pipeline hook.

    Uses Sentinel Hub via data_sources.py:

    - extracts VV mean for pre-period
    - extracts VV mean for post-period
    """

    mid = start + (end - start) / 2

    pre_vv = get_sentinel1_vv_mean(bbox, start, mid)
    post_vv = get_sentinel1_vv_mean(bbox, mid, end)

    return pre_vv, post_vv


# ----------------------------
# FINAL FLOOD SCORE
# ----------------------------

def compute_flood_score(data: FloodDetectionInput) -> float:
    """
    Insurance-grade flood score (NO MOCKS).

    Inputs:
        - Sentinel-1 VV (real via Sentinel Hub)
        - rainfall anomaly (ERA5/CDS)

    Output:
        0.0 → no flood
        1.0 → severe flood
    """

    if data.start_datetime is None or data.end_datetime is None:
        raise ValueError("start_datetime and end_datetime are required for real Sentinel-1 analysis")

    pre_vv, post_vv = fetch_sentinel1_vv_pair(
        data.bbox,
        data.start_datetime,
        data.end_datetime,
    )

    flood_extent = compute_flood_extent(pre_vv, post_vv)
    intensity = compute_intensity(pre_vv, post_vv)
    rainfall = normalize_rainfall(data.rainfall_anomaly)

    score = (
        0.60 * flood_extent +
        0.25 * intensity +
        0.15 * rainfall
    )

    return round(_clamp(score), 4)