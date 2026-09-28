"""Runs the fetch + AI pipeline every FETCH_INTERVAL_MINUTES inside the web process."""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from . import config, fetcher

log = logging.getLogger("scheduler")


def pipeline() -> None:
    try:
        fetcher.run_once()
    except Exception:
        log.exception("fetch run failed")
    try:
        from . import ai  # added in stage 2
        ai.process_pending()
    except ImportError:
        pass
    except Exception:
        log.exception("AI run failed")


def start() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(
        pipeline, "interval", minutes=config.FETCH_INTERVAL_MINUTES,
        next_run_time=datetime.now(timezone.utc),  # also run right away on start
        max_instances=1, coalesce=True, id="pipeline",
    )
    sched.start()
    log.info("scheduler started, every %d minutes", config.FETCH_INTERVAL_MINUTES)
    return sched
