"""
src/core/cleaner.py — Sistema Global de Retención (Garbage Collector).

Se encarga de limpiar backups antiguos tanto en local como en la nube
basándose en las configuraciones globales (settings) de la base de datos.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

class GarbageCollector:
    """
    Políticas de retención global para limpieza de copias obsoletas.
    """

    @staticmethod
    def clean_local_backups(global_retention_days: int, job_name: str | None = None, job_retention_days: int | None = None, backups_dir: str = "backups") -> int:
        """
        Escanea el directorio local de backups y elimina los archivos .zip
        más antiguos que la retención configurada.
        
        Si se especifica `job_name` y `job_retention_days`, aplica ese límite 
        solo a los archivos de ese job. Si `job_retention_days` es nulo, 
        usa `global_retention_days`.
        """
        retention_days = job_retention_days if job_retention_days is not None else global_retention_days
        
        if retention_days <= 0:
            return 0
            
        deleted_count = 0
        target_dir = Path.cwd() / backups_dir
        
        if not target_dir.exists():
            return 0

        threshold_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        try:
            for file_path in target_dir.glob("*.zip"):
                # Si estamos filtrando por job, comprobamos que el archivo empiece por el nombre del job
                if job_name and not file_path.name.startswith(f"{job_name}_"):
                    continue
                    
                # Obtenemos el tiempo de modificación o creación
                file_time = file_path.stat().st_mtime
                file_dt = datetime.fromtimestamp(file_time, tz=timezone.utc)
                
                if file_dt < threshold_date:
                    try:
                        file_path.unlink()
                        log.info(f"🗑️ Eliminado backup antiguo local: {file_path.name}")
                        deleted_count += 1
                    except OSError as e:
                        log.error(f"Error al eliminar backup local '{file_path.name}': {e}")
        except Exception as e:
            log.error(f"Error inesperado escaneando directorio local: {e}")
            
        return deleted_count

    @staticmethod
    def clean_cloud_backups(global_retention_days: int, credentials_path: str, folder_id: str | None = None, job_name: str | None = None, job_retention_days: int | None = None) -> int:
        """
        Usa GoogleDriveDestination para listar y borrar los backups 
        en la nube que excedan el límite de `retention_days`.
        
        Args:
            retention_days: Número de días de retención permitidos en la nube.
            credentials_path: Ruta al archivo credentials.json.
            folder_id: Carpeta de Google Drive (opcional).
            
        Returns:
            int: Cantidad de archivos en la nube eliminados.
        """
        retention_days = job_retention_days if job_retention_days is not None else global_retention_days
        
        if retention_days <= 0:
            return 0
            
        deleted_count = 0
        try:
            from src.destinations.google_drive import GoogleDriveDestination
            
            # Instanciamos el destino
            drive_dest = GoogleDriveDestination(
                credentials_file=credentials_path, 
                folder_id=folder_id,
                retention_days=retention_days,
                job_name=job_name or "backup"
            )
            
            # La clase GoogleDriveDestination ya tiene la lógica de retención lista!
            deleted_ids = drive_dest.apply_retention()
            deleted_count = len(deleted_ids)
            
            for f_id in deleted_ids:
                log.info(f"☁️ Eliminado backup antiguo en la nube (Drive ID: {f_id})")
                
        except Exception as e:
            log.error(f"Error inesperado durante la limpieza en la nube: {e}")
            
        return deleted_count

    @staticmethod
    def run_retention_policy(db, global_settings: dict) -> int:
        """
        Itera sobre cada Job activo en la base de datos.
        Calcula la fecha de corte (dest_retention_days).
        Busca ejecuciones en RunHistory más antiguas que la fecha de corte y las borra,
        eliminando también el archivo físico o en Google Drive.
        """
        deleted_count = 0
        try:
            from src.db import crud
            from sqlalchemy import select
            from src.db.models import RunHistory
            
            jobs = crud.job_get_all(db)
            
            for job in jobs:
                retention_days = job.dest_retention_days or 0
                if retention_days <= 0:
                    continue  # 0 significa que no caducan nunca
                    
                cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)
                
                # Buscar ejecuciones más antiguas que la fecha de corte
                stmt = select(RunHistory).where(
                    RunHistory.job_id == job.id,
                    RunHistory.started_at < cutoff_date
                )
                old_runs = list(db.scalars(stmt).all())
                
                for run in old_runs:
                    # 1. Borrar archivo físico o en Drive
                    if run.backup_file_path:
                        try:
                            if "drive.google.com" in run.backup_file_path:
                                # Es un enlace de Google Drive
                                file_id = run.backup_file_path.split("/d/")[1].split("/")[0] if "/d/" in run.backup_file_path else None
                                if file_id:
                                    creds_path = global_settings.get("credentials_path", "credentials.json")
                                    from src.destinations.google_drive import GoogleDriveDestination
                                    gdrive = GoogleDriveDestination(credentials_file=creds_path)
                                    service = gdrive._get_service()
                                    service.files().delete(fileId=file_id, supportsAllDrives=True).execute()  # type: ignore
                                    log.info(f"☁️ Eliminado backup antiguo de GDrive: {file_id}")
                            else:
                                # Archivo local o carpeta sincronizada
                                file_path = Path(run.backup_file_path)
                                if file_path.exists():
                                    if file_path.is_dir():
                                        import shutil
                                        shutil.rmtree(file_path, ignore_errors=True)
                                        log.info(f"🗑️ Eliminada carpeta antigua local: {file_path}")
                                    else:
                                        file_path.unlink()
                                        log.info(f"🗑️ Eliminado archivo antiguo local: {file_path.name}")
                        except Exception as e:
                            log.error(f"Error borrando archivo físico para Run {run.id}: {e}")
                    
                    # 2. Borrar registro de la Base de Datos
                    crud.run_delete(db, run.id)
                    deleted_count += 1
                    
        except Exception as exc:
            log.error(f"Error crítico en el Garbage Collector: {exc}")
            
        return deleted_count
