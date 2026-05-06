"""
src/processors/__init__.py

Paquete de procesadores de archivos para SolbaBackups.

Los procesadores transforman el archivo de dump antes de enviarlo
al destino final: comprimen y/o encriptan el contenido.
"""

from src.processors.compressor import Compressor
from src.processors.encryptor import Encryptor

__all__ = ["Compressor", "Encryptor"]
