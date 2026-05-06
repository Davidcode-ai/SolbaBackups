"""
src/destinations/google_drive.py — Destino Google Drive.

Implementa ``BaseDestination`` para subir backups a Google Drive usando
la API oficial de Google Drive v3.

Flujo de autenticación OAuth2:
    1. Primera vez: El usuario obtiene un ``credentials.json`` desde la
       Google Cloud Console (tipo «Desktop app»).
    2. La app inicia el flujo OAuth2 PKCE y guarda el token en ``token.json``.
    3. Las ejecuciones siguientes usan el ``token.json`` guardado,
       refrescándolo automáticamente cuando expira.

Almacenamiento en Drive:
    Los backups se guardan en la carpeta configurada (``folder_id``).
    Si no se especifica ``folder_id``, se sube a la raíz del Drive.
    Estructura opcional: ``{folder_id}/{job_name}/{backup_file}``

Política de retención en Drive:
    Usa la API de Drive para listar archivos por nombre de job y fecha
    de creación, eliminando los más antiguos que ``retention_days`` días
    con ``files.delete(fileId=...)`.

Dependencias:
    - ``google-auth``
    - ``google-auth-oauthlib``
    - ``google-api-python-client``

Extra params reconocidos:
    - ``folder_id``:          ID de la carpeta de Drive donde subir.
    - ``credentials_json``:   Contenido del ``credentials.json`` como string JSON.
    - ``token_json``:         Contenido del ``token.json`` guardado (refresh token).
    - ``chunk_size_mb``:      Tamaño del chunk para subidas resumibles (defecto: 5 MB).
"""

import json
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.destinations.base import BaseDestination

log = logging.getLogger(__name__)

# Scopes necesarios (solo permisos sobre archivos creados por esta app)
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveDestination(BaseDestination):
    """
    Destino para subir backups a Google Drive via API v3.

    Usa subidas resumibles (resumable uploads) para archivos grandes,
    lo que permite reanudar la subida si se interrumpe la conexión.
    """

    def __init__(
        self,
        credentials_json: str,
        token_json: str | None = None,
        folder_id: str | None = None,
        retention_days: int | None = None,
        job_name: str = "backup",
        chunk_size_mb: int = 5,
    ) -> None:
        """
        Inicializa el destino de Google Drive.

        Args:
            credentials_json: Contenido del ``credentials.json`` (OAuth2 Desktop app)
                              como string JSON serializado.
            token_json:       Contenido del ``token.json`` guardado de sesiones previas.
                              Si es ``None``, se iniciará el flujo OAuth2 interactivo.
            folder_id:        ID de la carpeta de Drive donde subir los backups.
                              ``None`` = raíz del Drive del usuario.
            retention_days:   Días de retención de backups en Drive.
            job_name:         Nombre del job para organizar archivos en Drive.
            chunk_size_mb:    Tamaño de chunk para subidas resumibles.
        """
        pass

    def upload(self, file_path: Path) -> str:
        """
        Sube el archivo de backup a Google Drive usando subida resumible.

        Detecta automáticamente el tipo MIME. Para archivos comprimidos
        usa ``application/zip`` o ``application/gzip``.

        Args:
            file_path: Ruta local al archivo de backup.

        Returns:
            str: URL de visualización del archivo en Google Drive
                 (``https://drive.google.com/file/d/{file_id}/view``).

        Raises:
            Exception: Si falla la autenticación o la subida.
        """
        pass

    def test_connection(self) -> bool:
        """
        Verifica que las credenciales de Google Drive son válidas.

        Intenta obtener el ``about`` del Drive (endpoint liviano que
        confirma autenticación sin acceder a archivos).

        Returns:
            bool: ``True`` si las credenciales son válidas y el Drive es accesible.
        """
        pass

    def apply_retention(self) -> list[str]:
        """
        Elimina de Drive los backups más antiguos que ``retention_days`` días.

        Busca archivos en la carpeta configurada cuyo nombre empiece por
        el nombre del job y cuya ``createdTime`` sea anterior al umbral.

        Returns:
            list[str]: IDs de Drive de los archivos eliminados.
        """
        pass

    def list_backups(self) -> list[dict]:
        """
        Lista los backups del job en la carpeta de Drive configurada.

        Returns:
            list[dict]: Backups con name, size_bytes, created_at, id (=Drive file ID).
        """
        pass

    def _get_credentials(self) -> Credentials:
        """
        Obtiene o refresca las credenciales OAuth2 de Google.

        Lógica:
            1. Si hay ``token_json`` guardado y el token es válido, lo usa.
            2. Si el token expiró pero hay ``refresh_token``, lo refresca.
            3. Si no hay token, inicia el flujo OAuth2 interactivo con PKCE.

        Returns:
            Credentials: Credenciales válidas listas para usar con la API.

        Raises:
            google.auth.exceptions.RefreshError: Si el refresh token es inválido.
        """
        pass

    def _build_service(self):
        """
        Construye el cliente de la API de Google Drive v3.

        Returns:
            Resource: Cliente de la API de Google Drive listo para usar.
        """
        pass

    def _get_or_create_job_folder(self, service) -> str:
        """
        Obtiene o crea la subcarpeta del job dentro de la carpeta configurada.

        Busca una carpeta con nombre ``{job_name}`` dentro de ``folder_id``.
        Si no existe, la crea.

        Args:
            service: Cliente de la API de Google Drive.

        Returns:
            str: ID de la carpeta del job en Google Drive.
        """
        pass
