"""Scheduler — runs sync at configurable intervals using APScheduler."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import Config

logger = logging.getLogger(__name__)

JOB_ID = "score_sync"


class SyncScheduler:
    """Manages scheduled and manual score syncing with adaptive frequency."""

    def __init__(
        self,
        sync_fn: Callable[[], None],
        has_live_sessions_fn: Optional[Callable[[], bool]] = None,
    ):
        self.sync_fn = sync_fn
        self.has_live_sessions_fn = has_live_sessions_fn
        self.scheduler = BackgroundScheduler(timezone=Config.SYNC_TIMEZONE)
        self._lock = threading.Lock()
        self._is_live_mode = False
        self._regular_interval = Config.SYNC_INTERVAL_MINUTES * 60
        self._live_interval = Config.SYNC_LIVE_INTERVAL_SECONDS

    def start(self):
        self._schedule_job(self._regular_interval)
        self.scheduler.start()
        logger.info(
            f"Scheduler started — regular sync every {Config.SYNC_INTERVAL_MINUTES} min, "
            f"live sync every {Config.SYNC_LIVE_INTERVAL_SECONDS}s"
        )

    def stop(self):
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:
            pass
        logger.info("Scheduler stopped")

    def trigger_now(self):
        logger.info("Manual sync triggered")
        thread = threading.Thread(target=self._safe_sync, daemon=True)
        thread.start()

    def _schedule_job(self, interval_seconds: int):
        trigger = IntervalTrigger(seconds=interval_seconds)
        if self.scheduler.get_job(JOB_ID):
            self.scheduler.reschedule_job(JOB_ID, trigger=trigger)
        else:
            self.scheduler.add_job(
                self._safe_sync,
                trigger=trigger,
                id=JOB_ID,
                name="F1 Score Sync",
                replace_existing=True,
            )

    def _check_and_adapt_interval(self):
        if not self.has_live_sessions_fn:
            return
        try:
            live_now = self.has_live_sessions_fn()
        except Exception:
            return

        if live_now and not self._is_live_mode:
            self._is_live_mode = True
            self._schedule_job(self._live_interval)
            logger.info(f"⚡ Live session detected! Switching to {self._live_interval}s sync")
        elif not live_now and self._is_live_mode:
            self._is_live_mode = False
            self._schedule_job(self._regular_interval)
            logger.info(f"No live sessions — switching back to {Config.SYNC_INTERVAL_MINUTES} min sync")

    def _safe_sync(self):
        try:
            self.sync_fn()
        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
        finally:
            self._check_and_adapt_interval()

    @property
    def next_run_time(self) -> Optional[str]:
        job = self.scheduler.get_job(JOB_ID)
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None

    @property
    def is_live_mode(self) -> bool:
        return self._is_live_mode
