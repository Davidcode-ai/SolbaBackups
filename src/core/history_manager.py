"""
src/core/history_manager.py — Audit trail and execution logs.

Thin wrapper around CRUD helpers for ``RunHistory`` and ``LogEntry`` rows used
by :class:`~src.core.job_manager.JobManager` and API routers.
"""

import datetime

from sqlalchemy.orm import Session
from src.db import crud


class HistoryManager:
    """Create runs and append timestamped log lines for backup execution."""

    def start_run(self, db: Session, job_id: int, job_name: str, trigger_type: str = "manual"):
        """Insert a new run row in ``running`` state.

        Args:
            db: Active SQLAlchemy session.
            job_id: Owning job primary key.
            job_name: Denormalized job name for UI/history lists.
            trigger_type: How the run was started (e.g. ``manual``, ``scheduled``).

        Returns:
            The ORM ``RunHistory`` instance created by :func:`~src.db.crud.run_create`.
        """
        return crud.run_create(db, job_id=job_id, job_name=job_name, trigger=trigger_type)

    def add_log(
        self,
        db: Session,
        run_id: int,
        level: str,
        message: str,
        stage: str = "general",
        timestamp: datetime.datetime | None = None,
    ):
        """Append one log line to a run's history.

        Args:
            db: Active SQLAlchemy session.
            run_id: Target run id.
            level: Severity label (e.g. ``INFO``, ``ERROR``).
            message: Human-readable detail.
            stage: Pipeline stage tag for filtering in the UI.
            timestamp: UTC time of the event; defaults to ``utcnow()`` if omitted.

        Returns:
            The ORM log row from :func:`~src.db.crud.log_add`.

        Note:
            Uses naive UTC timestamps for compatibility with the existing schema.
        """
        if timestamp is None:
            timestamp = datetime.datetime.utcnow()
        return crud.log_add(db, run_id, level, stage, message, timestamp=timestamp)

    def finish_run(
        self,
        db: Session,
        run_id: int,
        status: str,
        file_size_bytes: int = None,
        backup_file_path: str = None,
        error_message: str = None,
    ):
        """Close a run with final status and optional artifact metadata.

        Args:
            db: Active SQLAlchemy session.
            run_id: Run to finalize.
            status: Terminal state (e.g. ``success``, ``failed``).
            file_size_bytes: Optional size of produced backup.
            backup_file_path: Optional local path or remote URL of the artifact.
            error_message: Optional failure text when ``status`` is not success.

        Returns:
            Updated run row from :func:`~src.db.crud.run_finish`.
        """
        return crud.run_finish(
            db,
            run_id,
            status,
            file_size_bytes=file_size_bytes,
            backup_file_path=backup_file_path,
            error_message=error_message,
        )
