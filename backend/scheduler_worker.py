import os
import time
import socket
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from models import SessionLocal, ScheduledAutomation, ScheduledRun
from scheduler_dispatcher import SchedulerJobDispatcher
from scheduler_utils import calculate_next_runs

logger = logging.getLogger("cleansheet.scheduler_worker")

# Lease duration for distributed locking (3 minutes)
LEASE_DURATION_SECONDS = 180

def get_worker_id() -> str:
    return f"{socket.gethostname()}_{os.getpid()}"

class SchedulerWorker:
    """
    Independent persistent scheduler worker.
    Uses PostgreSQL transaction / lease locks to guarantee that multiple concurrent workers
    never double-execute the same schedule.
    Safe against crashes: expired leases are automatically reclaimed.
    """

    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or get_worker_id()
        self._running = False

    def acquire_due_jobs(self, db: Session, limit: int = 10) -> List[ScheduledAutomation]:
        """
        Finds active automations whose next_run_at <= now, and acquires a distributed lease.
        Reclaims abandoned locks if locked_until < now.
        """
        now_utc = datetime.now(timezone.utc)
        lease_expiration = now_utc + timedelta(seconds=LEASE_DURATION_SECONDS)

        # Query candidates that are active, due, and not locked by another active lease
        query = db.query(ScheduledAutomation).filter(
            ScheduledAutomation.is_active == 1,
            ScheduledAutomation.next_run_at <= now_utc,
            or_(
                ScheduledAutomation.locked_until == None,
                ScheduledAutomation.locked_until < now_utc
            )
        )

        candidates = query.limit(limit).all()
        acquired = []

        for auto in candidates:
            # Atomic update to claim the lease
            rows_updated = db.query(ScheduledAutomation).filter(
                ScheduledAutomation.id == auto.id,
                or_(
                    ScheduledAutomation.locked_until == None,
                    ScheduledAutomation.locked_until < now_utc
                )
            ).update({
                ScheduledAutomation.locked_until: lease_expiration,
                ScheduledAutomation.locked_by: self.worker_id
            }, synchronize_session=False)

            if rows_updated > 0:
                acquired.append(auto)

        db.commit()
        return acquired

    def process_automation(self, db: Session, automation: ScheduledAutomation) -> None:
        """
        Processes a single acquired automation and schedules its next run time.
        """
        scheduled_time = automation.next_run_at or datetime.now(timezone.utc)
        logger.info(f"Worker {self.worker_id} executing automation {automation.id} ('{automation.name}') scheduled for {scheduled_time}")

        try:
            # Execute job through strict decoupled dispatcher
            result = SchedulerJobDispatcher.execute_job(
                db=db,
                automation=automation,
                scheduled_for=scheduled_time,
                trigger_type="scheduled"
            )
            logger.info(f"Execution result for automation {automation.id}: {result.get('status')}")

        except Exception as e:
            logger.error(f"Unexpected error running automation {automation.id}: {e}")
        finally:
            # Advance next_run_at and release lease
            try:
                next_runs = calculate_next_runs(
                    schedule_type=automation.schedule_type,
                    cron_expr=automation.cron_expression,
                    timezone_name=automation.timezone_name,
                    start_from_utc=datetime.now(timezone.utc),
                    count=1
                )
                automation.next_run_at = next_runs[0] if next_runs else None
            except Exception as ex:
                logger.error(f"Failed to calculate next run for {automation.id}: {ex}")
                automation.next_run_at = None

            # Release lease
            automation.locked_until = None
            automation.locked_by = None
            db.commit()

    def run_once(self) -> int:
        """
        Executes a single polling iteration across all due jobs.
        Returns the number of jobs processed.
        """
        db = SessionLocal()
        try:
            due_jobs = self.acquire_due_jobs(db)
            for job in due_jobs:
                self.process_automation(db, job)
            return len(due_jobs)
        finally:
            db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    worker = SchedulerWorker()
    logger.info(f"Starting standalone scheduler worker (ID: {worker.worker_id})")
    
    # Standalone daemon loop
    try:
        while True:
            processed = worker.run_once()
            time.sleep(5 if processed == 0 else 1)
    except KeyboardInterrupt:
        logger.info("Worker stopped by signal.")
