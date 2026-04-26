from __future__ import annotations

from datetime import datetime, timezone
import logging
import json
from pathlib import Path
from typing import Any, Dict

import httpx

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DEMO_ALERTS_FILE = DATA_DIR / "alert_events.jsonl"


def _build_alert_payload(area: Dict[str, Any], previous_status: str | None) -> Dict[str, Any]:
    return {
        "event": "high_risk_transition",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "area_id": area.get("id"),
        "label": area.get("label"),
        "bbox": area.get("bbox"),
        "previous_status": previous_status,
        "current_status": area.get("flood_status"),
        "flood_score": area.get("flood_score"),
        "estimated_water_height_m": area.get("estimated_water_height_m"),
        "confidence": area.get("confidence"),
        "last_checked": area.get("last_checked"),
    }


def _send_ntfy_message(client: httpx.Client, url: str, payload: Dict[str, Any]) -> None:
    title = f"WaterCore Alert: {payload.get('label', 'Tracked area')} is HIGH risk"
    body = (
        f"Area: {payload.get('label')}\n"
        f"Score: {payload.get('flood_score')}\n"
        f"Height: {payload.get('estimated_water_height_m')} m\n"
        f"Confidence: {payload.get('confidence')}\n"
        f"Checked at: {payload.get('last_checked')}\n"
    )
    headers = {
        "Title": title,
        "Priority": "urgent",
        "Tags": "warning,water,flood",
    }
    response = client.post(url, content=body.encode("utf-8"), headers=headers)
    response.raise_for_status()


def _dispatch_alert_payload(payload: Dict[str, Any]) -> bool:
    """Send payload to configured alert webhook. Returns True on successful send."""
    settings = get_settings()

    if not settings.alerts_enabled:
        return False

    webhook_url = settings.alerts_webhook_url.strip()
    if not webhook_url:
        logger.warning("Alerts enabled but ALERTS_WEBHOOK_URL is empty")
        return False

    try:
        with httpx.Client(timeout=settings.alerts_timeout_seconds) as client:
            if "ntfy.sh" in webhook_url:
                _send_ntfy_message(client, webhook_url, payload)
            else:
                response = client.post(webhook_url, json=payload)
                response.raise_for_status()

        return True
    except Exception as exc:
        logger.error("Failed to send alert payload: %s", exc)
        return False


def _append_demo_alert(payload: Dict[str, Any], channel: str) -> None:
    """Persist alert event to local demo log for hackathon showcasing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        **payload,
        "channel": channel,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(DEMO_ALERTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def send_high_risk_notification(area: Dict[str, Any], previous_status: str | None) -> bool:
    """
    Send push notification for HIGH-risk transition via configured webhook.

    If webhook URL contains ntfy.sh, sends an ntfy-compatible message.
    Otherwise sends JSON payload to generic webhook.
    """
    payload = _build_alert_payload(area, previous_status)
    sent = _dispatch_alert_payload(payload)

    if sent:
        logger.info(
            "High-risk alert sent for area id=%s label=%s",
            payload.get("area_id"),
            payload.get("label"),
        )
        return True

    return False


def simulate_high_risk_notification(area: Dict[str, Any], previous_status: str | None = "MEDIUM") -> Dict[str, Any]:
    """
    Hackathon helper: simulate a HIGH-risk alert.

    - Attempts real webhook push if configured.
    - Always stores a local demo alert event in data/alert_events.jsonl.
    """
    payload = _build_alert_payload(area, previous_status)
    payload["event"] = "high_risk_simulation"

    sent_real = _dispatch_alert_payload(payload)
    channel = "webhook" if sent_real else "local-demo"
    _append_demo_alert(payload, channel=channel)

    return {
        "simulated": True,
        "sent_real": sent_real,
        "channel": channel,
        "demo_log_file": str(DEMO_ALERTS_FILE),
        "payload": payload,
    }
