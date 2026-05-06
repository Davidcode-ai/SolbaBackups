"""
src/db/__init__.py

Paquete de persistencia local de SolbaBackups.

Gestiona el ciclo de vida de la base de datos SQLite embebida
(``solba_data.db``) usando SQLAlchemy como ORM.
"""

from src.db.database import Base, SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db"]
