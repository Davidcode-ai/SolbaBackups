"""
src/destinations/base.py — Clase Abstracta Base para Destinos de Backup.

Define el contrato que deben cumplir todos los destinos de almacenamiento.
El ``JobManager`` usa esta interfaz para subir el archivo de backup final
al destino configurado en cada job, sin conocer los detalles de implementación.

Contrato del destino:
    1. ``upload(file_path)``    : Sube/copia el archivo al destino.
    2. ``test_connection()``    : Verifica que el destino es accesible.
    3. ``apply_retention()``    : Aplica la política de retención (elimina backups antiguos).
    4. ``list_backups()``       : Lista los backups existentes en el destino.

Política de retención:
    Cada destino implementa su propia lógica de retención basada en:
    - ``retention_days``: Elimina archivos más antiguos de N días.
    Los archivos se identifican como backups por su prefijo o extensión.
"""

import abc
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class BaseDestination(abc.ABC):
    """
    Clase abstracta base para todos los destinos de almacenamiento de backups.

    Atributos de instancia comunes:
        _retention_days: Número de días de retención. ``None`` = sin límite.
        _job_name:       Nombre del job, usado como prefijo/carpeta en el destino.
    """

    def __init__(
        self,
        retention_days: int | None = None,
        job_name: str = "backup",
    ) -> None:
        """
        Inicializa los parámetros comunes de todos los destinos.

        Args:
            retention_days: Días que se conservan los backups.
                            ``None`` significa sin límite de retención.
            job_name:       Nombre del job, usado para organizar los backups
                            (como carpeta o prefijo de nombre de archivo).
        """
        pass

    @abc.abstractmethod
    def upload(self, file_path: Path) -> str:
        """
        Sube o copia el archivo de backup al destino.

        Args:
            file_path: Ruta local al archivo de backup a subir.
                       El archivo existe y es legible al llamar este método.

        Returns:
            str: Identificador de destino del archivo guardado.
                 Para ``local``: ruta absoluta en el sistema de destino.
                 Para ``google_drive``: ID del archivo en Drive o URL de visualización.

        Raises:
            IOError:      Si falla la escritura en destino local.
            Exception:    Si falla la subida a la nube.
            FileNotFoundError: Si ``file_path`` no existe.
        """
        pass

    @abc.abstractmethod
    def test_connection(self) -> bool:
        """
        Verifica que el destino es accesible y se puede escribir en él.

        Para destinos locales: verifica que la carpeta existe y tiene permisos.
        Para destinos en nube: verifica que las credenciales son válidas.

        Returns:
            bool: ``True`` si el destino está disponible y escribible.
        """
        pass

    @abc.abstractmethod
    def apply_retention(self) -> list[str]:
        """
        Aplica la política de retención eliminando backups más antiguos que ``retention_days``.

        Solo actúa si ``retention_days`` no es ``None``.

        Returns:
            list[str]: Lista de identificadores (rutas o IDs) de los backups eliminados.
        """
        pass

    @abc.abstractmethod
    def list_backups(self) -> list[dict]:
        """
        Lista todos los backups existentes en el destino.

        Returns:
            list[dict]: Lista de diccionarios con información de cada backup:
                        ``{"name": str, "size_bytes": int, "created_at": datetime, "id": str}``
        """
        pass
