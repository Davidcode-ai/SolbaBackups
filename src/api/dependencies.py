"""
src/api/dependencies.py — Dependencias de Inyección para FastAPI.

Define los proveedores (callables) que FastAPI resuelve automáticamente
en los parámetros de las funciones de ruta usando ``Depends()``.

Dependencias disponibles:
    - ``get_db``        : Proporciona una sesión de SQLAlchemy con gestión
                          automática de commit/rollback/cierre.
    - ``get_scheduler`` : Proporciona acceso a la instancia global del
                          APScheduler para que los routers puedan registrar
                          o cancelar tareas programadas.
    - ``get_job_manager``: Proporciona la instancia del JobManager para
                           disparar ejecuciones manuales desde la API.

Patrón de uso en un router:
    ```python
    from fastapi import Depends
    from sqlalchemy.orm import Session
    from src.api.dependencies import get_db

    @router.get("/jobs")
    def list_jobs(db: Session = Depends(get_db)):
        ...
    ```
"""

import logging
from collections.abc import Generator

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from src.core.job_manager import JobManager
from src.db.database import SessionLocal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Instancias globales (singleton por proceso)
# ---------------------------------------------------------------------------
# Estas instancias se inicializan en el lifespan de server.py y se
# acceden aquí a través de las funciones de dependencia.
_scheduler: BackgroundScheduler | None = None
_job_manager: JobManager | None = None


def get_db() -> Generator[Session, None, None]:
    """
    Generador de sesiones de SQLAlchemy para inyección en rutas FastAPI.

    Abre una nueva sesión de BD para cada request HTTP y garantiza que
    siempre se cierre al terminar, independientemente de si hubo error.

    Yields:
        Session: Sesión de SQLAlchemy lista para usar.

    Example:
        ```python
        @router.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
        ```
    """
    pass


def get_scheduler() -> BackgroundScheduler:
    """
    Devuelve la instancia global del APScheduler.

    El scheduler se inicializa en el lifespan de la aplicación FastAPI
    (``server.py``) y se almacena en ``_scheduler``. Esta función actúa
    como puente de inyección.

    Returns:
        BackgroundScheduler: Instancia activa del scheduler.

    Raises:
        RuntimeError: Si el scheduler no ha sido inicializado todavía
                      (error de configuración en el arranque).
    """
    pass


def get_job_manager() -> JobManager:
    """
    Devuelve la instancia global del JobManager.

    El JobManager se inicializa junto con el scheduler en el lifespan.
    Proporciona el método ``run_job(job_id)`` para ejecuciones manuales.

    Returns:
        JobManager: Instancia activa del gestor de jobs.

    Raises:
        RuntimeError: Si el JobManager no ha sido inicializado todavía.
    """
    pass


def set_scheduler(scheduler: BackgroundScheduler) -> None:
    """
    Registra la instancia del scheduler creada en el lifespan.

    Esta función es llamada exclusivamente desde ``server.py`` durante
    el arranque de la aplicación.

    Args:
        scheduler: Instancia de APScheduler ya iniciada (``scheduler.start()``
                   debe haberse llamado previamente).
    """
    pass


def set_job_manager(job_manager: JobManager) -> None:
    """
    Registra la instancia del JobManager creada en el lifespan.

    Args:
        job_manager: Instancia de JobManager completamente inicializada.
    """
    pass
