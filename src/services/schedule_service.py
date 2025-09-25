from datetime import datetime, timedelta
from typing import Any, Dict, List

import structlog
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config.config import config
from src.exceptions.scheduler import JobSchedulingError
from src.utils.utils import utils
from src.utils.singleton import Singleton

logger = structlog.get_logger(__name__)


class ScheduleService(Singleton):
    """
    Service for managing all scheduled jobs.
    """

    def __init__(self):
        """Initialize the schedule service."""
        super().__init__()

        if hasattr(self, "_schedule_initialized"):
            return

        job_store = {"default": MemoryJobStore()}
        executors = {"default": AsyncIOExecutor()}
        job_defaults = {"coalesce": False, "max_instances": 1, "misfire_grace_time": 30}

        self.scheduler = AsyncIOScheduler(
            jobstores=job_store,
            executors=executors,
            job_defaults=job_defaults,
            timezone="UTC"
        )

        self.job_history: List[Dict[str, Any]] = []
        self.max_history_entries = 1000

        self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)

        logger.info("Schedule service initialized")

    def _job_executed_listener(self, event):
        """Handle successful job execution events."""
        job_info = {
            "job_id": event.job_id,
            "scheduled_run_time": event.scheduled_run_time.isoformat(),
            "status": "success",
            "retval": str(event.retval) if event.retval else None,
        }
        self._add_job_history(job_info)
        logger.info("Job executed successfully", **job_info)

    def _job_error_listener(self, event):
        """Handle job execution errors."""
        job_info = {
            "job_id": event.job_id,
            "scheduled_run_time": event.scheduled_run_time.isoformat(),
            "status": "error",
            "exception": str(event.exception),
            "traceback": event.traceback,
        }
        self._add_job_history(job_info)
        logger.error("Job execution failed", **job_info)

    def _add_job_history(self, job_info: Dict[str, Any]):
        """Add job execution info to history."""
        self.job_history.append(job_info)
        if len(self.job_history) > self.max_history_entries:
            self.job_history.pop(0)

    async def start(self):
        """Start the scheduler and schedule jobs."""
        logger.info("Starting scheduler service")
        try:
            self.scheduler.start()
            self._schedule_jobs()
            
            # Check if backfill is needed by querying the database
            try:
                is_backfill_complete = await utils.is_backfill_complete()
                if not is_backfill_complete:
                    self._schedule_backfill()
                    logger.info("Backfill job scheduled due to historical data incomplete")
                else:
                    logger.info("Backfill skipped due to historical data already exists")
            except Exception as e:
                logger.warning("Could not check backfill status, scheduling backfill as precaution", error=str(e))
                self._schedule_backfill()
            
            scheduled_jobs = self.scheduler.get_jobs()
            logger.info(
                "Scheduler started successfully",
                scheduled_job_count=len(scheduled_jobs),
                jobs=[job.id for job in scheduled_jobs]
            )

        except Exception as e:
            logger.error("Failed to start scheduler", error=str(e))
            raise JobSchedulingError(f"Failed to start scheduler: {str(e)}")

    def stop(self):
        """Stop the scheduler."""
        try:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler stopped")

        except Exception as e:
            logger.error("Failed to stop scheduler", error=str(e))
            raise JobSchedulingError(f"Failed to stop scheduler: {str(e)}")

    def _schedule_jobs(self):
        """Schedule all recurring jobs."""
        logger.info(
            "Scheduling recurring jobs",
            update_interval_hours=config.update_interval_hours
        )
        
        self.scheduler.add_job(
            utils.run_hourly_update,
            trigger=IntervalTrigger(hours=config.update_interval_hours),
            id="hourly_weather_update",
            name="Hourly Weather Data Update",
            replace_existing=True,
        )
        logger.info("Hourly weather update job scheduled")

        # Schedule daily cleanup
        self.scheduler.add_job(
            self.run_daily_cleanup,
            trigger=CronTrigger(hour=2, minute=0),
            id="daily_cleanup",
            name="Daily Cleanup",
            replace_existing=True,
        )
        logger.info("Daily cleanup job scheduled to run at 02:00 UTC")

        # Schedule weekly stats update
        self.scheduler.add_job(
            utils.run_weekly_stats_update,
            trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="weekly_stats_update",
            name="Weekly Stats Update",
            replace_existing=True,
        )
        logger.info("Weekly stats update job scheduled to run on Sundays at 03:00 UTC")

    def _schedule_backfill(self):
        """Schedule the one-time historical data backfill job."""
        run_date = datetime.now() + timedelta(seconds=10)
        self.scheduler.add_job(
            utils.run_backfill,
            trigger=DateTrigger(run_date=run_date),
            id="historical_backfill",
            name="Historical Data Backfill",
            replace_existing=True,
        )
        logger.info("Historical data backfill job scheduled", run_date=run_date.isoformat())

    def run_daily_cleanup(self):
        """Perform daily cleanup of old job history entries."""
        logger.info("Starting daily cleanup of job history")
        try:
            cutoff_date = datetime.now() - timedelta(days=7)
            initial_count = len(self.job_history)

            self.job_history = [
                job for job in self.job_history
                if datetime.fromisoformat(job.get("run_time")) > cutoff_date
            ]

            cleaned_count = initial_count - len(self.job_history)
            logger.info("Daily job history cleanup completed", cleaned_entries=cleaned_count)

            return {"status": "success", "cleaned_entries": cleaned_count}

        except Exception as e:
            logger.error("Daily job history cleanup failed", error=str(e))
            return {"status": "error", "error": str(e)}

    def get_job_status(self) -> Dict[str, Any]:
        """
        Get current job status and statistics.
        """
        jobs = [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in self.scheduler.get_jobs()
        ]

        return {
            "is_running": self.scheduler.running,
            "scheduled_jobs": jobs,
            "recent_job_history": self.job_history[-10:] if len(self.job_history) > 10 else None,
            "total_job_history_entries": len(self.job_history),
        }


schedule_service = ScheduleService()
