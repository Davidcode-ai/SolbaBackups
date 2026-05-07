"""
src/core/history_manager.py — Gestor de Auditoría y Logs.

Proporciona una capa de abstracción sobre las operaciones CRUD de logs,
encapsulando la lógica de creación de historial y eventos en la base de datos.
"""

from sqlalchemy.orm import Session
from src.db import crud


class HistoryManager:
    """Gestiona la creación de registros de ejecución y logs."""

    def start_run(self, db: Session, job_id: int, job_name: str, trigger_type: str = "manual"):
        """Inicia un registro de ejecución en estado RUNNING."""
        return crud.run_create(db, job_id=job_id, job_name=job_name, trigger=trigger_type)

    def add_log(self, db: Session, run_id: int, level: str, message: str, stage: str = "general"):
        """Añade una entrada de log al historial de la ejecución actual."""
        return crud.log_add(db, run_id, level, stage, message)

    def finish_run(self, db: Session, run_id: int, status: str, file_size_bytes: int = None, backup_file_path: str = None, error_message: str = None):
        """Finaliza el registro de ejecución actualizando su estado a SUCCESS o FAILED."""
        return crud.run_finish(
            db, 
            run_id, 
            status, 
            file_size_bytes=file_size_bytes, 
            backup_file_path=backup_file_path, 
            error_message=error_message
        )
