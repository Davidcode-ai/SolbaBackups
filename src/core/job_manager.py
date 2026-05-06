"""
src/core/job_manager.py — Orquestador del Pipeline de Backup.

Contiene la lógica central del JobManager que une la base de datos,
los conectores, compresores y destinos.
"""

import asyncio
import logging
import shutil
import tempfile
import traceback
from pathlib import Path

from sqlalchemy.orm import Session

from src.db import crud
from src.processors.compressor import Compressor

log = logging.getLogger(__name__)

class JobManager:
    """
    Orquesta la ejecución de un Job de backup (Pipeline completo).
    Versión Inicial Funcional (Simulación de Dump).
    """

    def __init__(self):
        self.compressor = Compressor()

    async def run_job(self, job_id: int, db_session: Session, trigger: str = "manual") -> None:
        """
        Ejecuta el pipeline de backup para el job especificado.
        
        Pasos:
        1. Lee configuración del DB.
        2. Crea RunHistory.
        3. Simula Dump SQL en temporal.
        4. Comprime el Dump.
        5. Mueve a carpeta /backups final.
        6. Actualiza estado (Éxito o Error).
        """
        # 1. Leer Job desde la base de datos
        job = crud.job_get_by_id(db_session, job_id)
        if not job:
            log.error(f"Job {job_id} no encontrado en la base de datos.")
            return

        log.info(f"Iniciando ejecución del Job '{job.name}' (ID: {job.id})")

        # 2. Crear RunHistory como 'RUNNING'
        run = crud.run_create(db_session, job_id=job.id, job_name=job.name, trigger=trigger)
        crud.log_add(db_session, run.id, "INFO", "init", f"Iniciando Job: {job.name} (Motor: {job.db_type})")

        try:
            # 3. Extracción de BD (Dump)
            crud.log_add(db_session, run.id, "INFO", "dump", f"Iniciando volcado de la BD '{job.db_name}' usando conector {job.db_type}...")
            
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
                
            # Llamada asíncrona a la extracción (capturará errores por subprocess stderr)
            await connector.extract(job, dump_path)
            
            dump_size = dump_path.stat().st_size
            crud.log_add(db_session, run.id, "INFO", "dump", f"Volcado completado: {dump_path.name} ({dump_size} bytes)")

            # 4. Comprimir el Archivo
            crud.log_add(db_session, run.id, "INFO", "compress", "Iniciando compresión en formato ZIP...")
            compressed_path = self.compressor.compress(dump_path)
            file_size = compressed_path.stat().st_size
            crud.log_add(db_session, run.id, "INFO", "compress", f"Compresión exitosa. Tamaño final: {file_size} bytes.")

            # 5. Mover a destino (Carpeta local o red / Google Drive)
            crud.log_add(db_session, run.id, "INFO", "upload", f"Preparando transferencia a destino '{job.dest_type}'...")
            
            if job.dest_type == "local":
                from src.destinations.local import LocalDestination
                destination = LocalDestination()
                # Ruta de destino: si el usuario no especificó, usamos cwd()/backups por defecto
                dest_path_str = job.dest_local_path or str(Path.cwd() / "backups")
            elif job.dest_type == "google_drive":
                raise NotImplementedError("Google Drive no está implementado aún.")
            else:
                raise NotImplementedError(f"Destino '{job.dest_type}' no implementado aún.")
                
            # Formatear el nombre del archivo para que sea único
            timestamp = run.started_at.strftime("%Y%m%d_%H%M%S")
            final_name = f"{job.name}_{timestamp}.sql.zip"
            
            # Renombramos el comprimido temporalmente al nombre final antes de subirlo
            final_temp_path = compressed_path.parent / final_name
            compressed_path = compressed_path.rename(final_temp_path)
            
            # Subir el archivo
            await destination.upload(compressed_path, dest_path_str)
            final_dest = str(Path(dest_path_str) / final_name)
            crud.log_add(db_session, run.id, "INFO", "upload", f"Transferencia exitosa a: {final_dest}")
            
            # Limpieza del dump original si no se borró
            if dump_path.exists():
                dump_path.unlink()
                
            # Limpieza del archivo comprimido temporal si la carga copió en lugar de mover
            if compressed_path.exists():
                compressed_path.unlink()

            # 6. Política de Retención
            if job.dest_retention_days and job.dest_retention_days > 0:
                crud.log_add(db_session, run.id, "INFO", "cleanup", f"Ejecutando política de retención ({job.dest_retention_days} días)...")
                deleted = await destination.clean_old_backups(dest_path_str, job.dest_retention_days)
                if deleted > 0:
                    crud.log_add(db_session, run.id, "INFO", "cleanup", f"Borrados {deleted} backups antiguos exitosamente.")
                else:
                    crud.log_add(db_session, run.id, "INFO", "cleanup", "No se encontraron backups antiguos que borrar.")

            crud.log_add(db_session, run.id, "INFO", "done", "Backup almacenado y pipeline completado.")

            # 7. Actualizar RunHistory a 'SUCCESS'
            crud.run_finish(
                db_session, 
                run.id, 
                status="success", 
                file_size_bytes=file_size,
                backup_file_path=str(final_dest)
            )
            log.info(f"Job '{job.name}' (ID: {job.id}) finalizado con éxito.")

        except Exception as e:
            error_msg = f"Excepción fatal en el pipeline: {str(e)}"
            log.error(error_msg)
            log.error(traceback.format_exc())
            
            # Registrar el error en base de datos para que la API/Frontend lo vean
            crud.log_add(db_session, run.id, "ERROR", "error", error_msg)
            
            # Actualizar RunHistory a 'FAILED'
            crud.run_finish(db_session, run.id, status="failed", error_message=error_msg)
