"""
Background scheduler for daily flood area checks.
Runs check_all_areas() daily at midnight UTC.

NOTE: Requires apscheduler. If not installed, scheduler skips gracefully.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
scheduler = None

# Try to import apscheduler; if not available, scheduler will be disabled
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    logger.warning("apscheduler not installed. Daily flood checks will be manual only.")


def start_scheduler():
    """Start the background scheduler for daily area checks."""
    global scheduler
    
    if not HAS_APSCHEDULER:
        logger.info("Scheduler disabled (apscheduler not installed). Use /api/v1/flood/check-areas for manual checks.")
        return
    
    if scheduler is not None and scheduler.running:
        logger.info("Scheduler already running")
        return
    
    try:
        from backend.app.services.area_tracking import check_all_areas
        
        scheduler = BackgroundScheduler()
        
        # Schedule daily check at 00:00 UTC
        scheduler.add_job(
            _run_daily_check,
            "cron",
            hour=0,
            minute=0,
            timezone="UTC",
            id="daily_flood_check",
            name="Daily flood area check",
        )
        
        scheduler.start()
        logger.info("Flood area scheduler started - daily check at 00:00 UTC")
    
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")


def stop_scheduler():
    """Stop the background scheduler."""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")


def _run_daily_check():
    """Task executed daily by scheduler."""
    try:
        from backend.app.services.area_tracking import check_all_areas
        
        logger.info(f"Starting daily area check at {datetime.now(timezone.utc).isoformat()}")
        updated_areas = check_all_areas()
        
        high_risk = [a for a in updated_areas if a.get("flood_status") == "HIGH"]
        logger.info(f"Daily check complete: {len(updated_areas)} areas checked, {len(high_risk)} HIGH RISK")
        
        for area in high_risk:
            logger.warning(f"HIGH FLOOD RISK - Area: {area['label']}, Score: {area['flood_score']}")
    
    except Exception as e:
        logger.error(f"Daily area check failed: {e}")
