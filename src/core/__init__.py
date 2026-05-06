"""
src/core/__init__.py

Paquete de lógica de negocio central de SolbaBackups.

Contiene el orquestador de Jobs, el executor en background y los modelos
Pydantic compartidos entre la API y los procesadores internos.
"""

from src.core.job_manager import JobManager
from src.core.models import JobCreate, JobRead, JobUpdate, RunHistoryRead

__all__ = ["JobManager", "JobCreate", "JobRead", "JobUpdate", "RunHistoryRead"]
