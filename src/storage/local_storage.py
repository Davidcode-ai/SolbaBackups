"""
Almacenamiento local: gestión del directorio de backups.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class LocalStorage:
    """Gestiona el directorio local de copias de seguridad."""

    def __init__(self, backup_dir: Path) -> None:
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def list_backups(self, pattern: str = "*") -> List[Dict[str, Any]]:
        """Lista los archivos de backup disponibles."""
        results = []
        for file in sorted(self.backup_dir.glob(pattern)):
            stat = file.stat()
            results.append(
                {
                    "name": file.name,
                    "path": file,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime),
                }
            )
        return results

    def purge_old(self, retention_days: int, pattern: str = "*") -> int:
        """
        Elimina backups más antiguos que retention_days.

        Returns:
            Número de archivos/directorios eliminados.
        """
        cutoff = datetime.now().timestamp() - retention_days * 86400
        removed = 0
        for item in self.backup_dir.glob(pattern):
            if item.stat().st_mtime < cutoff:
                try:
                    if item.is_dir():
                        import shutil

                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    removed += 1
                    logger.info("Backup antiguo eliminado: %s", item.name)
                except OSError as exc:
                    logger.warning("No se pudo eliminar %s: %s", item, exc)
        return removed

    def disk_usage(self) -> Dict[str, int]:
        """Devuelve estadísticas de uso de disco del directorio de backups."""
        total_size = 0
        count = 0
        for file in self.backup_dir.rglob("*"):
            if file.is_file():
                total_size += file.stat().st_size
                count += 1
        return {"files": count, "total_bytes": total_size}
