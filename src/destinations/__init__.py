"""
src/destinations/__init__.py

Paquete de destinos de backup para SolbaBackups.

Cada destino sabe cómo recibir un archivo de backup ya procesado
(comprimido y/o encriptado) y almacenarlo o subirlo.

Exports públicos:
    - BaseDestination    : Clase abstracta base.
    - LocalDestination   : Almacenamiento en carpeta local o de red.
    - GoogleDriveDestination : Subida a Google Drive via API v3.
    - get_destination    : Factory function que resuelve el destino correcto.
"""

from src.destinations.base import BaseDestination
from src.destinations.google_drive import GoogleDriveDestination
from src.destinations.local import LocalDestination

__all__ = [
    "BaseDestination",
    "LocalDestination",
    "GoogleDriveDestination",
    "get_destination",
]


def get_destination(destination_type: str, **kwargs) -> "BaseDestination":
    """
    Factory function que instancia el destino correcto según su tipo.

    Args:
        destination_type: Identificador del destino.
                          Valores aceptados: 'local', 'google_drive'.
        **kwargs: Parámetros de configuración del destino (ruta, credenciales, etc.)

    Returns:
        BaseDestination: Instancia del destino correspondiente.

    Raises:
        ValueError: Si ``destination_type`` no corresponde a ningún destino registrado.
    """
    pass
