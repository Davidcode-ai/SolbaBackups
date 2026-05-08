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
