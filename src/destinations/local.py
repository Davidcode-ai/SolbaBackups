"""
src/destinations/local.py — Destino de Almacenamiento Local.

Implementa ``BaseDestination`` para guardar backups en una carpeta local
del sistema de archivos (puede ser una ruta local, una unidad de red
mapeada o una ruta UNC de Windows como ``\\\\servidor\\carpeta``).

Comportamiento:
    - Crea la carpeta de destino si no existe (incluyendo directorios padres).
    - Organiza los backups en subcarpetas por nombre de job:
      ``{dest_path}/{job_name}/{backup_file}``
    - Aplica retención eliminando archivos con ``mtime`` más antiguo que
      ``retention_days`` días.

Compatibilidad Windows:
    - Soporta rutas UNC (``\\\\server\\share``).
    - Soporta rutas con letras de unidad (``D:\\backups``).
    - Maneja permisos de acceso denegado con error descriptivo.

Seguridad:
    - Valida que la ruta de destino no sea un subdirectorio del directorio
      temporal de trabajo para evitar sobrescribir archivos en proceso.
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from src.destinations.base import BaseDestination

log = logging.getLogger(__name__)


class LocalDestination(BaseDestination):
    """
    Destino para guardar backups en una carpeta local o de red.

    Args de configuración (pasados via kwargs al constructor):
        path (str | Path): Ruta a la carpeta de destino. Requerido.
    """

    def __init__(
        self,
        path: str | Path,
        retention_days: int | None = None,
        job_name: str = "backup",
    ) -> None:
        """
        Inicializa el destino local.

        Args:
            path:           Ruta a la carpeta donde guardar los backups.
            retention_days: Días de retención. ``None`` = sin límite.
            job_name:       Nombre del job para crear subcarpeta.
        """
        pass

    def upload(self, file_path: Path) -> str:
        """
        Copia el archivo de backup a la carpeta de destino.

        Crea la estructura de directorios si no existe:
        ``{self._dest_path}/{self._job_name}/``

        Tras copiar el archivo, llama automáticamente a ``apply_retention()``
        para mantener limpio el destino.

        Args:
            file_path: Ruta local al archivo de backup a copiar.

        Returns:
            str: Ruta absoluta al archivo copiado en el destino.

        Raises:
            FileNotFoundError: Si ``file_path`` no existe.
            PermissionError:   Si no hay permisos de escritura en el destino.
            OSError:           Si hay un error de red al escribir en ruta UNC.
        """
        pass

    def test_connection(self) -> bool:
        """
        Verifica que la carpeta de destino es accesible y escribible.

        Intenta crear un archivo temporal ``.solba_test`` y lo elimina
        inmediatamente para verificar permisos de escritura.

        Returns:
            bool: ``True`` si la carpeta es accesible y escribible.
        """
        pass

    def apply_retention(self) -> list[str]:
        """
        Elimina backups más antiguos que ``retention_days`` días.

        Busca todos los archivos en la carpeta de destino del job y elimina
        los que tienen ``mtime`` anterior al umbral de retención.

        Returns:
            list[str]: Rutas de los archivos eliminados.
        """
        pass

    def list_backups(self) -> list[dict]:
        """
        Lista todos los archivos de backup en la carpeta de destino.

        Returns:
            list[dict]: Lista de backups con name, size_bytes, created_at, id (=ruta).
        """
        pass

    def _ensure_dest_dir(self) -> Path:
        """
        Crea la carpeta de destino del job si no existe.

        La estructura es: ``{self._dest_path}/{self._job_name}/``

        Returns:
            Path: Ruta al directorio creado/verificado.

        Raises:
            PermissionError: Si no se pueden crear los directorios.
        """
        pass
