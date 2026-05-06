"""
src/db/database.py — Configuración del Motor SQLAlchemy.

Configura la conexión a la base de datos SQLite local (``solba_data.db``)
y expone los objetos fundamentales de SQLAlchemy necesarios en toda la app.

Objetos exportados:
    - ``engine``      : Motor de BD SQLAlchemy (singleton por proceso).
    - ``SessionLocal``: Fábrica de sesiones de BD (no thread-safe por defecto,
                        FastAPI gestiona una por request via Depends).
    - ``Base``        : Clase declarativa base de la que heredan todos los
                        modelos ORM.
    - ``get_db``      : Generador de sesiones para inyección de dependencias
                        (también disponible en ``src.api.dependencies``).
"""

import logging
import os
import sys
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

log = logging.getLogger(__name__)


def resolve_db_path() -> Path:
    """
    Resuelve la ruta absoluta del archivo ``solba_data.db``.
    """
    if "SOLBA_DB_PATH" in os.environ:
        return Path(os.environ["SOLBA_DB_PATH"])
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "solba_data.db"
    return Path.cwd() / "solba_data.db"


class Base(DeclarativeBase):
    """Clase base declarativa de SQLAlchemy para todos los modelos ORM."""
    pass


def create_db_engine():
    """
    Crea y configura el motor SQLAlchemy para SQLite.
    Habilita WAL mode para mejor concurrencia.
    """
    db_path = resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{db_path}"

    eng = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=(os.environ.get("SOLBA_DEBUG") == "1"),
    )

    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return eng


# ---------------------------------------------------------------------------
# Singletons del módulo (se inicializan al importar)
# ---------------------------------------------------------------------------
engine = create_db_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def init_db() -> None:
    """Crea todas las tablas definidas en ``src/db/models.py`` si no existen."""
    # Importar los modelos aquí asegura que estén registrados en Base.metadata
    from src.db.models import AppSetting, Job, LogEntry, RunHistory
    Base.metadata.create_all(bind=engine)
    log.info("Base de datos inicializada correctamente.")


def get_db() -> Generator[Session, None, None]:
    """Generador de sesiones para inyección de dependencias de FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
