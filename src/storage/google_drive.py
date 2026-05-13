"""
Módulo de subida a Google Drive.

Flujo de autenticación:
  1. La primera vez abre el navegador para que el usuario autorice.
  2. Guarda el token en token.json para sesiones posteriores.

Operaciones disponibles:
  - upload_file(local_path, folder_id)  → sube un archivo
  - list_files(folder_id)               → lista archivos en una carpeta
  - delete_file(file_id)                → elimina un archivo remoto
  - find_or_create_folder(name, parent) → localiza / crea una carpeta
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Alcances necesarios para subir/eliminar archivos
_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveUploader:
    """Gestiona la subida de archivos a Google Drive."""

    def __init__(
        self,
        credentials_file: str = "credentials.json",
        token_file: str = "token.json",
    ) -> None:
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self._service = None  # Lazy init

    # ------------------------------------------------------------------
    # Autenticación
    # ------------------------------------------------------------------
    def _get_service(self):
        """Obtiene (o crea) el servicio autenticado de Google Drive."""
        if self._service is not None:
            return self._service

        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise ImportError(
                "Instala las dependencias de Google Drive:\n"
                "  pip install google-api-python-client google-auth-oauthlib"
            ) from exc

        creds: Optional[Credentials] = None

        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), _SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_file.exists():
                    raise FileNotFoundError(
                        f"No se encontró {self.credentials_file}. "
                        "Descarga las credenciales OAuth 2.0 desde "
                        "Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_file), _SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(self.token_file, "w", encoding="utf-8") as fh:
                fh.write(creds.to_json())

        self._service = build("drive", "v3", credentials=creds)
        return self._service

    # ------------------------------------------------------------------
    # Operaciones
    # ------------------------------------------------------------------
    def upload_file(
        self,
        local_path: Path,
        folder_id: str = "",
        mime_type: str = "application/octet-stream",
    ) -> Optional[str]:
        """
        Sube un archivo a Google Drive.

        Returns:
            ID del archivo subido, o None si hubo un error.
        """
        from googleapiclient.http import MediaFileUpload  # noqa: PLC0415

        service = self._get_service()
        metadata: Dict[str, Any] = {"name": local_path.name}
        if folder_id:
            metadata["parents"] = [folder_id]

        media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)
        try:
            file_obj = (
                service.files()
                .create(body=metadata, media_body=media, fields="id")
                .execute()
            )
            file_id: str = file_obj.get("id", "")
            logger.info("Archivo subido a Drive: %s → id=%s", local_path.name, file_id)
            return file_id
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al subir %s a Drive: %s", local_path, exc)
            return None

    def list_files(
        self, folder_id: str = "", max_results: int = 100
    ) -> List[Dict[str, str]]:
        """
        Lista archivos en una carpeta de Google Drive.

        Returns:
            Lista de dicts con 'id', 'name', 'mimeType', 'modifiedTime'.
        """
        service = self._get_service()
        query = f"'{folder_id}' in parents and trashed=false" if folder_id else ""
        try:
            response = (
                service.files()
                .list(
                    q=query,
                    pageSize=max_results,
                    fields="files(id, name, mimeType, modifiedTime)",
                )
                .execute()
            )
            files: List[Dict[str, str]] = response.get("files", [])
            return files
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al listar archivos en Drive: %s", exc)
            return []

    def delete_file(self, file_id: str) -> bool:
        """Elimina un archivo de Google Drive por su ID."""
        service = self._get_service()
        try:
            service.files().delete(fileId=file_id).execute()
            logger.info("Archivo eliminado de Drive: %s", file_id)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al eliminar %s de Drive: %s", file_id, exc)
            return False

    def find_or_create_folder(self, name: str, parent_id: str = "") -> Optional[str]:
        """
        Busca una carpeta por nombre dentro de parent_id.
        Si no existe, la crea. Devuelve el ID de la carpeta.
        """
        service = self._get_service()
        query = (
            f"name='{name}' "
            "and mimeType='application/vnd.google-apps.folder' "
            "and trashed=false"
        )
        if parent_id:
            query += f" and '{parent_id}' in parents"
        try:
            resp = service.files().list(q=query, fields="files(id, name)").execute()
            files = resp.get("files", [])
            if files:
                folder_id: str = files[0]["id"]
                logger.debug("Carpeta Drive encontrada: %s (%s)", name, folder_id)
                return folder_id

            # Crear la carpeta
            metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            if parent_id:
                metadata["parents"] = [parent_id]
            folder = service.files().create(body=metadata, fields="id").execute()
            folder_id = folder.get("id", "")
            logger.info("Carpeta Drive creada: %s (%s)", name, folder_id)
            return folder_id
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al buscar/crear carpeta '%s': %s", name, exc)
            return None

    def upload_backup(
        self, local_path: Path, root_folder_id: str = ""
    ) -> Optional[str]:
        """
        Sube una copia de seguridad organizándola en subcarpetas por fecha.

        Estructura en Drive: <root_folder_id> / YYYY-MM / <archivo>
        """
        from datetime import datetime  # noqa: PLC0415

        month_folder_name = datetime.now().strftime("%Y-%m")
        month_folder_id = self.find_or_create_folder(month_folder_name, root_folder_id)
        return self.upload_file(local_path, folder_id=month_folder_id or "")
