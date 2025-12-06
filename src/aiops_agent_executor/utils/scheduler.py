"""Execution cleanup scheduler using APScheduler.

Provides scheduled cleanup of old execution records.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


class ExecutionCleanupScheduler:
    """Scheduler for cleaning up old execution records.

    Runs daily at 2:00 AM to remove execution records older than 30 days.
    """

    def __init__(
        self,
        session_factory: "async_sessionmaker[AsyncSession]",
        retention_days: int = 30,
    ) -> None:
        """Initialize the cleanup scheduler.

        Args:
            session_factory: SQLAlchemy async session factory
            retention_days: Number of days to retain execution records
        """
        self._session_factory = session_factory
        self._retention_days = retention_days
        self._scheduler = AsyncIOScheduler()
        self._is_running = False

    def start(self) -> None:
        """Start the scheduler."""
        if self._is_running:
            logger.warning("Scheduler is already running")
            return

        # Schedule cleanup job at 2:00 AM daily
        self._scheduler.add_job(
            self._cleanup_old_executions,
            trigger=CronTrigger(hour=2, minute=0),
            id="execution_cleanup",
            name="Clean up old execution records",
            replace_existing=True,
        )

        self._scheduler.start()
        self._is_running = True
        logger.info(
            "Execution cleanup scheduler started",
            extra={"retention_days": self._retention_days},
        )

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._is_running:
            return

        self._scheduler.shutdown(wait=True)
        self._is_running = False
        logger.info("Execution cleanup scheduler stopped")

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._is_running

    async def _cleanup_old_executions(self) -> None:
        """Clean up execution records older than retention period."""
        # Import here to avoid circular imports
        from aiops_agent_executor.db.models.team import Execution, ExecutionLog

        cutoff_date = datetime.now(UTC) - timedelta(days=self._retention_days)

        async with self._session_factory() as session:
            try:
                # First, get IDs of executions to delete
                stmt = select(Execution.id).where(Execution.created_at < cutoff_date)
                result = await session.execute(stmt)
                execution_ids = [row[0] for row in result.fetchall()]

                if not execution_ids:
                    logger.debug("No old executions to clean up")
                    return

                # Delete associated logs first (foreign key constraint)
                delete_logs_stmt = delete(ExecutionLog).where(
                    ExecutionLog.execution_id.in_(execution_ids)
                )
                logs_result = await session.execute(delete_logs_stmt)
                deleted_logs = logs_result.rowcount

                # Delete executions
                delete_executions_stmt = delete(Execution).where(
                    Execution.id.in_(execution_ids)
                )
                executions_result = await session.execute(delete_executions_stmt)
                deleted_executions = executions_result.rowcount

                await session.commit()

                logger.info(
                    "Cleaned up old execution records",
                    extra={
                        "deleted_executions": deleted_executions,
                        "deleted_logs": deleted_logs,
                        "cutoff_date": cutoff_date.isoformat(),
                    },
                )

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to clean up old executions: {e}")
                raise

    async def run_cleanup_now(self) -> int:
        """Run cleanup immediately (for testing).

        Returns:
            Number of executions deleted
        """
        from aiops_agent_executor.db.models.team import Execution, ExecutionLog

        cutoff_date = datetime.now(UTC) - timedelta(days=self._retention_days)
        deleted_count = 0

        async with self._session_factory() as session:
            # Get IDs first
            stmt = select(Execution.id).where(Execution.created_at < cutoff_date)
            result = await session.execute(stmt)
            execution_ids = [row[0] for row in result.fetchall()]

            if execution_ids:
                # Delete logs
                await session.execute(
                    delete(ExecutionLog).where(ExecutionLog.execution_id.in_(execution_ids))
                )

                # Delete executions
                result = await session.execute(
                    delete(Execution).where(Execution.id.in_(execution_ids))
                )
                deleted_count = result.rowcount

                await session.commit()

        return deleted_count
