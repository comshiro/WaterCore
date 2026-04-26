from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from backend.app.models.schemas import RiskInput, RiskResponse


@dataclass(frozen=True)
class RiskWeights:
    rainfall: float = 0.35
    soil_moisture: float = 0.25
    flood_signal: float = 0.25
    vegetation_stress: float = 0.15


def _clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(value, max_value))


def _normalize_anomaly(value: float) -> float:
    # Bound anomaly values to [0, 3] then scale to [0, 1].
    return _clamp(value / 3.0)


def classify_risk(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def compute_risk(input_data: RiskInput, threshold: float) -> RiskResponse:
    weights = RiskWeights()

    rainfall_component = _normalize_anomaly(input_data.rainfall_anomaly) * weights.rainfall
    soil_component = _normalize_anomaly(input_data.soil_moisture_anomaly) * weights.soil_moisture
    flood_component = _clamp(input_data.flood_signal) * weights.flood_signal
    vegetation_component = _clamp(input_data.vegetation_stress) * weights.vegetation_stress

    score = _clamp(rainfall_component + soil_component + flood_component + vegetation_component)

    factors: Dict[str, float] = {
        "rainfall_component": round(rainfall_component, 4),
        "soil_moisture_component": round(soil_component, 4),
        "flood_component": round(flood_component, 4),
        "vegetation_component": round(vegetation_component, 4),
        "threshold_gap": round(score - threshold, 4),
    }

    return RiskResponse(
        risk_score=round(score, 4),
        risk_level=classify_risk(score),
        threshold=round(threshold, 4),
        factors=factors,
        generated_at=datetime.utcnow(),
    )
