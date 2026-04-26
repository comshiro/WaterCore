from backend.app.models.schemas import RiskInput
from backend.app.services.risk_engine import classify_risk, compute_risk


def test_risk_engine_computation() -> None:
    sample = RiskInput(
        latitude=44.4,
        longitude=26.1,
        rainfall_anomaly=2.0,
        soil_moisture_anomaly=2.2,
        flood_signal=0.7,
        vegetation_stress=0.4,
    )

    response = compute_risk(sample, threshold=0.7)

    assert 0 <= response.risk_score <= 1
    assert response.risk_level in {"low", "medium", "high"}
    assert "threshold_gap" in response.factors


def test_risk_classification() -> None:
    assert classify_risk(0.2) == "low"
    assert classify_risk(0.6) == "medium"
    assert classify_risk(0.9) == "high"
