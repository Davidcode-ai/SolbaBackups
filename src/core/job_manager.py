"""
src/core/job_manager.py — Orquestador del Pipeline de Backup.

Contiene la lógica central del JobManager que une la base de datos,
los conectores, compresores y destinos.
"""

import os
import asyncio
import logging
import shutil
import tempfile
import traceback
from pathlib import Path

from src.db import crud
from src.db.database import SessionLocal
from src.processors.compressor import Compressor
from src.core.history_manager import HistoryManager

log = logging.getLogger(__name__)


class JobManager:
    """
    Orquesta la ejecución de un Job de backup (Pipeline completo).
    """

    def __init__(self):
        self.compressor = Compressor()

    async def run_job(self, job_id: int, trigger: str = "manual") -> None:
        """
        Ejecuta el pipeline de backup para el job especificado.
        Gestiona su propia sesión de BD (with SessionLocal() as db) 
        para no bloquear a los llamadores (ej. endpoints API).
        """
        history_manager = HistoryManager()
        
        with SessionLocal() as db:
            # 1. Leer Job desde la base de datos
            job = crud.job_get_by_id(db, job_id)
            if not job:
                log.error(f"Job {job_id} no encontrado en la base de datos.")
                return

            log.info(f"Iniciando ejecución del Job '{job.name}' (ID: {job.id})")

            # 2. Crear RunHistory como 'RUNNING'
            run = history_manager.start_run(db, job_id=job.id, job_name=job.name, trigger_type=trigger)
            history_manager.add_log(db, run.id, "INFO", f"Iniciando Job: {job.name} (Motor: {job.db_type})", stage="init")

            # TODO EL PROCESO ENVUELTO EN UN GRAN TRY-EXCEPT
            try:
                # 3. Extracción de BD (Dump)
                history_manager.add_log(db, run.id, "INFO", f"Iniciando volcado de la BD '{job.db_name}' usando conector {job.db_type}...", stage="dump")

                # Crear un archivo temporal donde el conector guardará el volcado SQL
                fd, dump_path_str = tempfile.mkstemp(suffix=".sql")
                os.close(fd)
                dump_path = Path(dump_path_str)

                # Seleccionar y ejecutar conector
                if job.db_type == "postgresql":
                    from src.connectors.postgresql import PostgreSQLConnector
                    connector = PostgreSQLConnector()
                elif job.db_type == "mysql":
                    from src.connectors.mysql import MySQLConnector
                    connector = MySQLConnector()
                else:
                    raise NotImplementedError(f"El conector para el motor '{job.db_type}' no está implementado aún.")

                # Llamada asíncrona a la extracción
                await connector.extract(job, dump_path)

                dump_size = dump_path.stat().st_size
                history_manager.add_log(db, run.id, "INFO", f"Volcado completado: {dump_path.name} ({dump_size} bytes)", stage="dump")

                # 4. Comprimir el Archivo
                history_manager.add_log(db, run.id, "INFO", "Iniciando compresión en formato ZIP...", stage="compress")
                compressed_path = self.compressor.compress(dump_path)
                file_size = compressed_path.stat().st_size
                history_manager.add_log(db, run.id, "INFO", f"Compresión exitosa. Tamaño final: {file_size} bytes.", stage="compress")

                # 5. Mover a destino (Carpeta local o red)
                history_manager.add_log(db, run.id, "INFO", f"Preparando transferencia a destino '{job.dest_type}'...", stage="upload")

                if job.dest_type == "local":
                    from src.destinations.local import LocalDestination
                    destination = LocalDestination()
                    # Ruta de destino por defecto si el usuario no especificó
                    dest_path_str = job.dest_local_path or str(Path.cwd() / "backups")
                elif job.dest_type == "google_drive":
                    raise NotImplementedError("Google Drive no está implementado aún.")
                else:
                    raise NotImplementedError(f"Destino '{job.dest_type}' no implementado aún.")

                # Formatear el nombre del archivo
                timestamp = run.started_at.strftime("%Y%m%d_%H%M%S")
                final_name = f"{job.name}_{timestamp}.sql.zip"

                # Renombramos el comprimido temporalmente al nombre final antes de subirlo
                final_temp_path = compressed_path.parent / final_name
                compressed_path = compressed_path.rename(final_temp_path)

                # Subir el archivo
                await destination.upload(compressed_path, dest_path_str)
                final_dest = str(Path(dest_path_str) / final_name)
                history_manager.add_log(db, run.id, "INFO", f"Transferencia exitosa a: {final_dest}", stage="upload")

                # Limpieza de archivos temporales
                if dump_path.exists():
                    dump_path.unlink()
                if compressed_path.exists():
                    compressed_path.unlink()

                # 6. Política de Retención
                if job.dest_retention_days and job.dest_retention_days > 0:
                    history_manager.add_log(db, run.id, "INFO", f"Ejecutando política de retención ({job.dest_retention_days} días)...", stage="cleanup")
                    deleted = await destination.clean_old_backups(dest_path_str, job.dest_retention_days)
                    if deleted > 0:
                        history_manager.add_log(db, run.id, "INFO", f"Borrados {deleted} backups antiguos exitosamente.", stage="cleanup")
                    else:
                        history_manager.add_log(db, run.id, "INFO", "No se encontraron backups antiguos que borrar.", stage="cleanup")

                history_manager.add_log(db, run.id, "INFO", "Backup almacenado y pipeline completado.", stage="done")

                # 7. Actualizar RunHistory a 'SUCCESS' si todo fue bien
                history_manager.finish_run(
                    db, 
                    run.id, 
                    status="success", 
                    file_size_bytes=file_size,
                    backup_file_path=str(final_dest)
                )
                log.info(f"Job '{job.name}' (ID: {job.id}) finalizado con éxito.")

            except Exception as e:
                # 8. Captura global de errores (Si cualquier paso falla)
                error_msg = f"Excepción fatal en el pipeline: {str(e)}"
                log.error(error_msg)
                log.error(traceback.format_exc())
                print(error_msg)  # Imprime por consola por si acaso

                # Registrar el error en base de datos para que la API/Frontend lo vean
                history_manager.add_log(db, run.id, "ERROR", error_msg, stage="error")
                
                # Actualizar RunHistory a 'FAILED'
                history_manager.finish_run(
                    db, run.id, status="failed", error_message=error_msg
                )
