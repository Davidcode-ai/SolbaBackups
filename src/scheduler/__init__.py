"""
src/scheduler/__init__.py

Paquete del scheduler de tareas programadas.
Exporta las funciones principales para uso desde el lifespan de FastAPI.
"""

from src.scheduler.job_scheduler import (
    create_scheduler,
    get_next_run_time,
    load_jobs_from_db,
    pause_job,
    resume_job,
    schedule_job,
    unschedule_job,
)

__all__ = [
    "create_scheduler",
    "load_jobs_from_db",
    "schedule_job",
    "unschedule_job",
    "pause_job",
    "resume_job",
    "get_next_run_time",
]
