"""
src/api/dependencies.py — Dependencias de Inyección para FastAPI.
"""

import logging
from collections.abc import Generator
from fastapi import Request
from sqlalchemy.orm import Session
from src.db.database import SessionLocal

from src.core.job_manager import JobManager

log = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """Proporciona una sesión de base de datos segura."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_job_manager(request: Request) -> JobManager:
    """Devuelve la instancia global del JobManager desde el estado de la app."""
    if not hasattr(request.app.state, "job_manager"):
        raise RuntimeError("El JobManager no ha sido inicializado en el arranque.")
    return request.app.state.job_manager
