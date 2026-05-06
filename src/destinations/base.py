"""
src/destinations/base.py — Interfaz Base de Destinos de Almacenamiento.
"""
from abc import ABC, abstractmethod
from pathlib import Path

class BaseDestination(ABC):
    """
    Clase abstracta que define el contrato para todos los destinos
    de almacenamiento de backups.
    """

    @abstractmethod
    async def upload(self, file_path: Path, destination_path: str) -> bool:
        """
        Sube o mueve un archivo al destino final.

        Args:
            file_path: Ruta local del archivo a subir (generalmente temporal/comprimido).
            destination_path: Ruta, carpeta o ID del destino donde almacenar.

        Returns:
            bool: True si la carga fue exitosa.
        """
        pass

    @abstractmethod
    async def clean_old_backups(self, destination_path: str, retention_days: int) -> int:
        """
        Limpia los backups antiguos que superen la política de retención.

        Args:
            destination_path: Ruta, carpeta o ID del destino.
            retention_days: Cantidad de días a conservar.

        Returns:
            int: Número de archivos borrados.
        """
        pass
