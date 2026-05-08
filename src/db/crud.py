"""
src/db/crud.py — Operaciones CRUD sobre la Base de Datos.

Centraliza todas las consultas y mutaciones de la BD para mantener
los routers de la API libres de lógica de persistencia.
"""

import datetime
import json
import logging
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.db.models import AppSetting, Job, LogEntry, RunHistory

log = logging.getLogger(__name__)

# ===========================================================================
# JOB CRUD
# ===========================================================================

def job_get_all(
    db: Session,
    is_active: bool | None = None,
    db_type: str | None = None,
) -> list[Job]:
    stmt = select(Job)
    if is_active is not None:
        stmt = stmt.where(Job.is_active == is_active)
    if db_type is not None:
        stmt = stmt.where(Job.db_type == db_type)
    stmt = stmt.order_by(Job.name.asc())
    return list(db.scalars(stmt).all())


def job_get_by_id(db: Session, job_id: int) -> Job | None:
    return db.get(Job, job_id)


def job_get_by_name(db: Session, name: str) -> Job | None:
    stmt = select(Job).where(Job.name == name)
    return db.scalars(stmt).first()


def job_create(db: Session, data: dict) -> Job:
    # Aplanar el objeto 'schedule' si viene anidado (desde el modelo Pydantic)
    schedule_data = data.pop("schedule", None)
    if schedule_data:
        data["schedule_type"] = schedule_data.get("schedule_type")
        data["schedule_cron"] = schedule_data.get("cron_expression")
        data["schedule_interval_minutes"] = schedule_data.get("interval_minutes")

    db_job = Job(**data)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


def job_update(db: Session, job_id: int, data: dict) -> Job | None:
    db_job = db.get(Job, job_id)
    if not db_job:
        return None

    # Aplanar el objeto 'schedule' si viene anidado
    schedule_data = data.pop("schedule", None)
    if schedule_data is not None:
        data["schedule_type"] = schedule_data.get("schedule_type")
        data["schedule_cron"] = schedule_data.get("cron_expression")
        data["schedule_interval_minutes"] = schedule_data.get("interval_minutes")

    for key, value in data.items():
        setattr(db_job, key, value)

    db_job.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_job)
    return db_job


def job_delete(db: Session, job_id: int) -> bool:
    db_job = db.get(Job, job_id)
    if not db_job:
        return False
    db.delete(db_job)
    db.commit()
    return True


def job_set_active(db: Session, job_id: int, is_active: bool) -> Job | None:
    db_job = db.get(Job, job_id)
    if not db_job:
        return None
    db_job.is_active = is_active
    db_job.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_job)
    return db_job


# ===========================================================================
# RUN HISTORY CRUD
# ===========================================================================

def run_create(db: Session, job_id: int, job_name: str, trigger: str = "manual") -> RunHistory:
    run = RunHistory(
        job_id=job_id,
        job_name=job_name,
        trigger=trigger,
        status="running",
        started_at=datetime.datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def run_finish(
    db: Session,
    run_id: int,
    status: str,
    file_size_bytes: int | None = None,
    backup_file_path: str | None = None,
    destination_url: str | None = None,
    error_message: str | None = None,
) -> RunHistory | None:
    run = db.get(RunHistory, run_id)
    if not run:
        return None

    now = datetime.datetime.utcnow()
    run.finished_at = now
    run.duration_secs = (now - run.started_at).total_seconds()
    run.status = status
    run.file_size_bytes = file_size_bytes
    run.backup_file_path = backup_file_path
    run.destination_url = destination_url
    run.error_message = error_message

    db.commit()
    db.refresh(run)
    return run


def run_get_all(
    db: Session,
    page: int = 1,
    page_size: int = 25,
    status_filter: str | None = None,
) -> list[RunHistory]:
    stmt = select(RunHistory)
    if status_filter:
        stmt = stmt.where(RunHistory.status == status_filter)
    stmt = stmt.order_by(desc(RunHistory.started_at)).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt).all())


def run_get_by_job(
    db: Session,
    job_id: int,
    page: int = 1,
    page_size: int = 25,
) -> list[RunHistory]:
    stmt = select(RunHistory).where(RunHistory.job_id == job_id)
    stmt = stmt.order_by(desc(RunHistory.started_at)).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt).all())


def run_get_by_id(db: Session, run_id: int) -> RunHistory | None:
    return db.get(RunHistory, run_id)


def run_delete(db: Session, run_id: int) -> bool:
    run = db.get(RunHistory, run_id)
    if not run:
        return False
    db.delete(run)
    db.commit()
    return True


def history_purge_old(db: Session, retention_days: int) -> int:
    """Elimina las ejecuciones (y sus logs por CASCADE) más antiguas que retention_days."""
    if retention_days <= 0:
        return 0
    
    cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)
    
    # Buscar ejecuciones antiguas
    stmt = select(RunHistory).where(RunHistory.started_at < cutoff_date)
    old_runs = list(db.scalars(stmt).all())
    
    count = len(old_runs)
    for run in old_runs:
        db.delete(run)
        
    db.commit()
    return count


# ===========================================================================
# LOG ENTRY CRUD
# ===========================================================================

def log_add(
    db: Session,
    run_id: int,
    level: str,
    stage: str,
    message: str,
) -> LogEntry:
    log_entry = LogEntry(
        run_id=run_id,
        level=level,
        stage=stage,
        message=message,
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def log_get_by_run(
    db: Session,
    run_id: int,
    level: str | None = None,
    stage: str | None = None,
    after_id: int = 0,
) -> list[LogEntry]:
    stmt = select(LogEntry).where(LogEntry.run_id == run_id, LogEntry.id > after_id)
    if level:
        stmt = stmt.where(LogEntry.level == level)
    if stage:
        stmt = stmt.where(LogEntry.stage == stage)
    stmt = stmt.order_by(LogEntry.id.asc())
    return list(db.scalars(stmt).all())


# ===========================================================================
# APP SETTINGS CRUD
# ===========================================================================

def setting_get(db: Session, key: str, default: Any = None) -> Any:
    setting = db.get(AppSetting, key)
    if setting is None:
        return default
    try:
        return json.loads(setting.value_json)
    except json.JSONDecodeError:
        return setting.value_json


def setting_set(db: Session, key: str, value: Any) -> AppSetting:
    setting = db.get(AppSetting, key)
    serialized = json.dumps(value)

    if setting:
        setting.value_json = serialized
        setting.updated_at = datetime.datetime.utcnow()
    else:
        setting = AppSetting(key=key, value_json=serialized)
        db.add(setting)

    db.commit()
    db.refresh(setting)
    return setting


def setting_get_all(db: Session) -> dict[str, Any]:
    stmt = select(AppSetting)
    settings = db.scalars(stmt).all()
    result = {}
    for s in settings:
        try:
            result[s.key] = json.loads(s.value_json)
        except json.JSONDecodeError:
            result[s.key] = s.value_json
    return result


def setting_set_many(db: Session, settings: dict[str, Any]) -> None:
    for key, value in settings.items():
        setting = db.get(AppSetting, key)
        serialized = json.dumps(value)
        if setting:
            setting.value_json = serialized
            setting.updated_at = datetime.datetime.utcnow()
        else:
            setting = AppSetting(key=key, value_json=serialized)
            db.add(setting)
    db.commit()
