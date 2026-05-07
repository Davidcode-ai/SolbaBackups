"""
src/connectors/base.py — Interfaz Base de Conectores de Bases de Datos.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from src.db.models import Job

class BaseConnector(ABC):
    """
    Clase abstracta que define el contrato para todos los conectores
    de extracción de bases de datos.
    """
    
    @abstractmethod
    async def extract(self, job: Job, output_file_path: Path) -> bool:
        """
        Extrae los datos de la base de datos configurada en el Job y
        los guarda en el archivo especificado.
        
        Args:
            job: Instancia del modelo Job con la configuración de conexión.
            output_file_path: Ruta absoluta donde se guardará el dump.
            
        Returns:
            bool: True si la extracción fue exitosa.
            
        Raises:
            Exception: Si ocurre un error fatal durante la extracción.
        """
        pass
