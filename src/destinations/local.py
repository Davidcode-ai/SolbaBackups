"""
src/destinations/local.py — Destino Carpeta Local / Red.
"""
import asyncio
import logging
import shutil
import time
from pathlib import Path

from src.destinations.base import BaseDestination

log = logging.getLogger(__name__)

class LocalDestination(BaseDestination):
    """
    Gestiona el almacenamiento en carpetas locales o rutas de red (UNC).
    """

    async def upload(self, file_path: Path, destination_path: str) -> bool:
        dest_dir = Path(destination_path)
        # Asegurar que el directorio destino existe
        dest_dir.mkdir(parents=True, exist_ok=True)

        final_path = dest_dir / file_path.name
        log.info(f"Moviendo backup local de {file_path} a {final_path}...")
        
        # Mover archivo de forma asíncrona usando un thread para evitar
        # bloquear el loop si destination_path es una unidad de red lenta.
        await asyncio.to_thread(shutil.move, str(file_path), str(final_path))
        
        return True

    async def clean_old_backups(self, destination_path: str, retention_days: int) -> int:
        if retention_days <= 0:
            return 0  # 0 o negativo significa sin límite de retención

        dest_dir = Path(destination_path)
        if not dest_dir.exists():
            return 0

        deleted_count = 0
        now = time.time()
        # Segundos correspondientes a retention_days (1 día = 86400 segundos)
        cutoff_time = now - (retention_days * 86400)

        # Buscar todos los archivos .zip en la carpeta
        for file_path in dest_dir.glob("*.zip"):
            if not file_path.is_file():
                continue
                
            try:
                # Comparamos la fecha de modificación del archivo
                mtime = file_path.stat().st_mtime
                if mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    log.debug(f"Backup antiguo eliminado: {file_path.name}")
            except Exception as e:
                log.error(f"Error al intentar eliminar el backup antiguo {file_path.name}: {e}")

        return deleted_count
