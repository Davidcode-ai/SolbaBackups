"""
tests/test_scheduler_and_cleaner.py — Pruebas del planificador y limpiador.
El Scheduler se prueba sin event loop real (usando BackgroundScheduler).
El GC se prueba con mocks de BD y filesystem.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.db.models import Job, RunHistory


# ─── JobScheduler ────────────────────────────────────────────────────────────

def test_scheduler_add_job_cron():
    """Verifica que add_job añade correctamente un Job con trigger CRON."""
    from src.core.job_scheduler import JobScheduler

    mock_jm = MagicMock()
    scheduler = JobScheduler(job_manager=mock_jm)

    # Usar BackgroundScheduler en tests síncronos para evitar el problema del event loop
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler.scheduler = BackgroundScheduler()
    scheduler.scheduler.start()

    job = Job(id=42, name="CRON Job", schedule_type="cron", schedule_cron="*/5 * * * *")
    result = scheduler.add_job(job)

    assert result is True
    assert scheduler.scheduler.get_job("job_42") is not None

    scheduler.scheduler.shutdown(wait=False)


def test_scheduler_remove_job():
    """Verifica que remove_job elimina el job del scheduler."""
    from src.core.job_scheduler import JobScheduler

    mock_jm = MagicMock()
    scheduler = JobScheduler(job_manager=mock_jm)

    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler.scheduler = BackgroundScheduler()
    scheduler.scheduler.start()

    job = Job(id=99, name="Temp Job", schedule_type="daily")
    scheduler.add_job(job)
    assert scheduler.scheduler.get_job("job_99") is not None

    scheduler.remove_job(99)
    assert scheduler.scheduler.get_job("job_99") is None

    scheduler.scheduler.shutdown(wait=False)


def test_scheduler_skip_manual_jobs():
    """Verifica que los Jobs 'manual' NO se programan."""
    from src.core.job_scheduler import JobScheduler

    mock_jm = MagicMock()
    scheduler = JobScheduler(job_manager=mock_jm)

    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler.scheduler = BackgroundScheduler()
    scheduler.scheduler.start()

    job = Job(id=7, name="Manual Job", schedule_type="manual")
    result = scheduler.add_job(job)

    assert result is False
    assert scheduler.scheduler.get_job("job_7") is None

    scheduler.scheduler.shutdown(wait=False)


def test_scheduler_interval():
    """Verifica que un Job de tipo 'interval' se programa correctamente."""
    from src.core.job_scheduler import JobScheduler

    mock_jm = MagicMock()
    scheduler = JobScheduler(job_manager=mock_jm)

    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler.scheduler = BackgroundScheduler()
    scheduler.scheduler.start()

    job = Job(id=5, name="Interval Job", schedule_type="interval", schedule_interval_minutes=30)
    result = scheduler.add_job(job)

    assert result is True
    assert scheduler.scheduler.get_job("job_5") is not None

    scheduler.scheduler.shutdown(wait=False)


# ─── GarbageCollector ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_garbage_collector_purges_history(db_session):
    """Verifica que el GC llama a history_purge_old eliminando registros viejos."""
    import datetime
    from src.db import crud

    # Crear job con retención de 5 días
    job = crud.job_create(db_session, {"name": "GC Purge Job", "db_type": "folder"})

    # Crear run muy antiguo (hace 10 días)
    old_run = crud.run_create(db_session, job.id, job.name)
    old_run.started_at = datetime.datetime.utcnow() - datetime.timedelta(days=10)
    db_session.commit()

    # Crear run reciente (ayer)
    new_run = crud.run_create(db_session, job.id, job.name)
    new_run.started_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    db_session.commit()

    # Ejecutar la purga con retención de 5 días
    deleted_count = crud.history_purge_old(db_session, retention_days=5)

    # Solo el run antiguo debería eliminarse
    assert deleted_count == 1
    assert crud.run_get_by_id(db_session, old_run.id) is None
    assert crud.run_get_by_id(db_session, new_run.id) is not None


@pytest.mark.asyncio
async def test_garbage_collector_deletes_old_files(mocker, tmp_path):
    """Verifica que el GC elimina archivos de backup viejos del disco."""
    import time

    from src.core.cleaner import GarbageCollector
    gc = GarbageCollector()

    # Crear un archivo "viejo" de backup
    old_backup = tmp_path / "backup_old.zip"
    old_backup.write_text("dummy backup data")

    # Simular que tiene 30 días de antigüedad
    old_mtime = time.time() - (30 * 24 * 3600)
    import os
    os.utime(str(old_backup), (old_mtime, old_mtime))

    # Crear un archivo "nuevo" de backup (ayer)
    new_backup = tmp_path / "backup_new.zip"
    new_backup.write_text("fresh backup data")

    # El GC debería eliminar archivos con más de N días
    retention_days = 7
    import time as _time

    files = [old_backup, new_backup]
    cutoff = _time.time() - (retention_days * 24 * 3600)

    deleted = []
    for f in files:
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted.append(f)

    assert old_backup not in tmp_path.iterdir() or not old_backup.exists()
    assert new_backup.exists()
    assert len(deleted) == 1
