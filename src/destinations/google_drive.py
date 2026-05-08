"""
src/destinations/google_drive.py — Destino Google Drive.

Implementa ``BaseDestination`` para subir backups a Google Drive usando
la API oficial de Google Drive v3.

Flujos de autenticación soportados:
    1. **Service Account** (recomendado para servidores desatendidos):
       El archivo ``credentials.json`` contiene ``type: service_account``.
       No requiere interacción del usuario.
    2. **OAuth2 Desktop App** (para uso personal/desarrollo):
       El archivo ``credentials.json`` contiene ``type: installed``.
       La primera ejecución abre el navegador para autorizar.
       El token se guarda en ``token.json`` y se refresca automáticamente.

Almacenamiento en Drive:
    Los backups se guardan en la carpeta configurada (``folder_id``).
    Si no se especifica, se sube a la raíz del Drive.
    Estructura: ``{folder_id}/{job_name}/{backup_file.zip}``

Política de retención:
    Usa la API de Drive para listar archivos por nombre de job y
    ``createdTime``, eliminando los más antiguos que ``retention_days``
    días con ``files.delete(fileId=...)``.

Subidas resumibles:
    Usa ``MediaFileUpload`` con ``resumable=True`` para soportar archivos
    grandes y reanudar subidas interrumpidas.

Dependencias en requirements.txt:
    google-api-python-client>=2.128.0
    google-auth>=2.29.0
    google-auth-oauthlib>=1.2.0
    google-auth-httplib2>=0.2.0
"""

from __future__ import annotations

import json
import logging
import mimetypes
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from google.auth.exceptions import DefaultCredentialsError, RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from src.destinations.base import BaseDestination

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
# Scope mínimo: sólo accede a archivos creados por esta app en el Drive.
# Para Service Account que necesite acceder a un Drive Compartido,
# podría ser necesario 'https://www.googleapis.com/auth/drive'.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Tamaño mínimo de chunk para subidas resumibles (múltiplo de 256 KiB).
_256_KiB = 256 * 1024

# Folder MIME type en Drive.
_FOLDER_MIME = "application/vnd.google-apps.folder"

# Ruta por defecto de los archivos de credenciales en la raíz del proyecto.
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CREDENTIALS_PATH = _BASE_DIR / "credentials.json"
_DEFAULT_TOKEN_PATH = _BASE_DIR / "token.json"


# ---------------------------------------------------------------------------
# Excepciones personalizadas
# ---------------------------------------------------------------------------
class GoogleDriveError(Exception):
    """Error base para todos los fallos de Google Drive."""


class CredentialsNotFoundError(GoogleDriveError):
    """El archivo credentials.json no existe o es inaccesible."""


class AuthenticationError(GoogleDriveError):
    """Falló el flujo de autenticación o el token es inválido."""


class UploadError(GoogleDriveError):
    """Falló la subida del archivo a Google Drive."""


class ConnectionError(GoogleDriveError):  # noqa: A001
    """No hay conectividad con la API de Google."""


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------
class GoogleDriveDestination(BaseDestination):
    """
    Destino para subir backups a Google Drive via API v3.

    Soporta autenticación por Service Account y OAuth2 Desktop App.
    Usa subidas resumibles para archivos grandes (tolerante a fallos de red).

    Args:
        credentials_json: Contenido del ``credentials.json`` como string JSON.
                          Si es ``None``, se lee desde ``credentials_file``.
        credentials_file: Ruta al archivo ``credentials.json``.
                          Ignorado si ``credentials_json`` se proporciona.
        token_json:       Contenido del ``token.json`` (OAuth2 refresh token)
                          como string JSON. Si es ``None``, se lee/escribe
                          desde ``token_file``.
        token_file:       Ruta al ``token.json`` para persistir el refresh token.
        folder_id:        ID de la carpeta raíz en Drive. ``None`` = raíz del Drive.
        retention_days:   Días de retención de backups. ``None`` = sin límite.
        job_name:         Nombre del job (se usa como subcarpeta en Drive).
        chunk_size_mb:    Tamaño del chunk para subidas resumibles (MiB).
    """

    def __init__(
        self,
        credentials_json: str | None = None,
        credentials_file: str | Path | None = None,
        token_json: str | None = None,
        token_file: str | Path | None = None,
        folder_id: str | None = None,
        retention_days: int | None = None,
        job_name: str = "backup",
        chunk_size_mb: int = 5,
    ) -> None:
        self._folder_id = folder_id
        self._retention_days = retention_days
        self._job_name = job_name
        self._chunk_size = max(chunk_size_mb * 1024 * 1024, _256_KiB)
        # Asegurar que chunk_size sea múltiplo de 256 KiB (requisito de la API).
        self._chunk_size = (self._chunk_size // _256_KiB) * _256_KiB

        # Resolver fuente de credentials.json
        self._credentials_json: str | None = credentials_json
        self._credentials_file = Path(credentials_file) if credentials_file else _DEFAULT_CREDENTIALS_PATH

        # Resolver fuente/destino de token.json
        self._token_json: str | None = token_json
        self._token_file = Path(token_file) if token_file else _DEFAULT_TOKEN_PATH

        # El servicio se construye de forma perezosa (lazy).
        self._service = None

        log.debug(
            "GoogleDriveDestination inicializado. folder_id=%s, job=%s, chunk=%d MiB",
            self._folder_id or "raíz",
            self._job_name,
            chunk_size_mb,
        )

    # -------------------------------------------------------------------------
    # Contrato BaseDestination
    # -------------------------------------------------------------------------
    def upload(self, file_path: Path) -> str:
        """
        Sube el archivo ``.zip`` de backup a Google Drive usando subida resumible.

        Crea (o reutiliza) automáticamente la subcarpeta del job dentro
        de la carpeta configurada, y aplica la política de retención tras
        cada subida exitosa.

        Args:
            file_path: Ruta local al archivo de backup. Debe existir.

        Returns:
            str: URL de visualización del archivo en Drive:
                 ``https://drive.google.com/file/d/{file_id}/view``

        Raises:
            FileNotFoundError:    Si ``file_path`` no existe.
            CredentialsNotFoundError: Si falta ``credentials.json``.
            AuthenticationError: Si la autenticación falla.
            ConnectionError:     Si no hay conectividad con Google.
            UploadError:         Si la subida falla por cualquier otro motivo.
        """
        if not file_path.exists():
            raise FileNotFoundError(
                f"El archivo de backup no existe: {file_path}"
            )
        if not file_path.is_file():
            raise ValueError(f"La ruta no es un archivo: {file_path}")

        log.info("⬆️  Iniciando subida a Google Drive: %s (%.1f MB)", file_path.name, file_path.stat().st_size / 1e6)

        service = self._get_service()

        # Resolver la carpeta destino (raíz del job).
        target_folder_id = self._get_or_create_job_folder(service)

        # Detectar MIME type del archivo.
        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        file_metadata: dict[str, Any] = {
            "name": file_path.name,
            "parents": [target_folder_id],
        }

        media = MediaFileUpload(
            str(file_path),
            mimetype=mime_type,
            chunksize=self._chunk_size,
            resumable=True,
        )

        try:
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id,webViewLink",
                supportsAllDrives=True
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    log.debug("  Progreso subida: %d%%", progress)

            file_id = response.get("id")
            web_view_link = response.get(
                "webViewLink",
                f"https://drive.google.com/file/d/{file_id}/view",
            )

            log.info("✅ Archivo subido exitosamente. file_id=%s", file_id)

            # Aplicar retención tras cada subida exitosa.
            deleted = self.apply_retention()
            if deleted:
                log.info("🗑️  Retención aplicada: %d archivo(s) eliminado(s).", len(deleted))

            return web_view_link

        except HttpError as exc:
            status_code = exc.resp.status
            log.error("Error HTTP de Drive API al subir '%s': %s %s", file_path.name, status_code, exc.reason)
            if status_code == 403:
                raise UploadError(
                    f"Sin permisos para subir a Drive (carpeta: {target_folder_id}). "
                    "Verifica los scopes de las credenciales."
                ) from exc
            raise UploadError(
                f"Error HTTP {status_code} al subir '{file_path.name}': {exc.reason}"
            ) from exc
        except (socket.timeout, socket.error, TransportError) as exc:
            log.error("Error de red al subir a Drive: %s", exc)
            raise ConnectionError(
                "No se pudo completar la subida: error de conectividad con Google Drive."
            ) from exc
        except Exception as exc:
            log.error("Error inesperado al subir '%s': %s", file_path.name, exc)
            raise UploadError(f"Error inesperado durante la subida: {exc}") from exc

    def upload_file(self, file_path: str, folder_id: str | None = None) -> dict[str, str]:
        """
        Alias de alto nivel compatible con la firma pedida en las instrucciones.

        Permite sobreescribir puntualmente el ``folder_id`` por llamada sin
        cambiar la configuración del objeto. Es el método que llamará el
        *JobManager* cuando el destino sea Google Drive.

        Args:
            file_path: Ruta (string) al archivo ``.zip`` a subir.
            folder_id: ID de carpeta de Drive (sobreescribe el configurado).

        Returns:
            dict con ``file_id`` y ``web_view_link``:
            ``{"file_id": "1xAbC...", "web_view_link": "https://drive.google.com/..."}``

        Raises:
            FileNotFoundError, CredentialsNotFoundError, AuthenticationError,
            ConnectionError, UploadError.
        """
        path = Path(file_path)

        # Sobreescribir folder_id puntualmente si se proporciona.
        original_folder_id = self._folder_id
        if folder_id is not None:
            self._folder_id = folder_id
            self._service = None  # Forzar rebuild si la carpeta cambia.

        try:
            service = self._get_service()
            target_folder_id = self._get_or_create_job_folder(service)

            if not path.exists():
                raise FileNotFoundError(f"El archivo de backup no existe: {path}")

            mime_type, _ = mimetypes.guess_type(str(path))
            mime_type = mime_type or "application/octet-stream"

            file_metadata: dict[str, Any] = {
                "name": path.name,
                "parents": [target_folder_id],
            }
            media = MediaFileUpload(
                str(path),
                mimetype=mime_type,
                chunksize=self._chunk_size,
                resumable=True,
            )

            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id,webViewLink",
                supportsAllDrives=True
            )

            response = None
            while response is None:
                _, response = request.next_chunk()

            file_id: str = response["id"]
            web_view_link: str = response.get(
                "webViewLink",
                f"https://drive.google.com/file/d/{file_id}/view",
            )

            log.info("✅ upload_file completado: file_id=%s", file_id)
            return {"file_id": file_id, "web_view_link": web_view_link}

        except (FileNotFoundError, GoogleDriveError):
            raise
        except HttpError as exc:
            raise UploadError(f"HTTP {exc.resp.status}: {exc.reason}") from exc
        except Exception as exc:
            raise UploadError(str(exc)) from exc
        finally:
            # Restaurar folder_id original.
            self._folder_id = original_folder_id

    def test_connection(self) -> bool:
        """
        Verifica que las credenciales son válidas y Drive es accesible.

        Llama a ``about.get()`` que es el endpoint más ligero de la API
        y confirma autenticación sin acceder a ningún archivo del usuario.

        Returns:
            bool: ``True`` si el Drive es accesible, ``False`` en caso contrario.
        """
        try:
            service = self._get_service()
            about = service.about().get(fields="user,storageQuota").execute()
            user_email = about.get("user", {}).get("emailAddress", "?")
            log.info("✅ Conexión a Google Drive OK. Usuario: %s", user_email)
            return True
        except (GoogleDriveError, HttpError, TransportError, socket.error) as exc:
            log.warning("❌ Test de conexión a Drive fallido: %s", exc)
            return False

    def clean_old_backups(self) -> None:
        """
        Elimina backups antiguos cumpliendo con el contrato de BaseDestination.
        Es un alias de apply_retention.
        """
        deleted = self.apply_retention()
        if deleted:
            log.info(f"Retención en Drive completada. {len(deleted)} archivos eliminados.")

    def apply_retention(self) -> list[str]:
        """
        Elimina de Drive los backups del job más antiguos que ``retention_days``.

        Solo actúa si ``retention_days`` no es ``None``. Busca archivos
        en la carpeta del job que tengan ``createdTime`` anterior al umbral.

        Returns:
            list[str]: IDs de Drive de los archivos eliminados.
        """
        if self._retention_days is None:
            return []

        try:
            service = self._get_service()
            job_folder_id = self._get_or_create_job_folder(service)

            threshold = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
            threshold_str = threshold.strftime("%Y-%m-%dT%H:%M:%SZ")

            query = (
                f"'{job_folder_id}' in parents "
                f"and mimeType != '{_FOLDER_MIME}' "
                f"and createdTime < '{threshold_str}' "
                f"and trashed = false"
            )

            results = (
                service.files()
                .list(q=query, fields="files(id,name,createdTime)", pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True)
                .execute()
            )
            files = results.get("files", [])
            deleted_ids: list[str] = []

            for file in files:
                fid = file["id"]
                fname = file["name"]
                try:
                    service.files().delete(fileId=fid, supportsAllDrives=True).execute()
                    deleted_ids.append(fid)
                    log.info("🗑️  Eliminado de Drive: %s (id=%s)", fname, fid)
                except HttpError as exc:
                    log.warning("No se pudo eliminar '%s' (id=%s): %s", fname, fid, exc)

            return deleted_ids

        except GoogleDriveError:
            raise
        except Exception as exc:
            log.error("Error aplicando retención en Drive: %s", exc)
            return []

    def list_backups(self) -> list[dict]:
        """
        Lista los backups del job en la carpeta de Drive configurada.

        Returns:
            list[dict]: Cada elemento contiene:
                - ``name`` (str): Nombre del archivo.
                - ``size_bytes`` (int): Tamaño en bytes.
                - ``created_at`` (datetime): Fecha de creación en UTC.
                - ``id`` (str): ID del archivo en Google Drive.
        """
        try:
            service = self._get_service()
            job_folder_id = self._get_or_create_job_folder(service)

            query = (
                f"'{job_folder_id}' in parents "
                f"and mimeType != '{_FOLDER_MIME}' "
                f"and trashed = false"
            )

            results = (
                service.files()
                .list(
                    q=query,
                    fields="files(id,name,size,createdTime)",
                    orderBy="createdTime desc",
                    pageSize=200,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                )
                .execute()
            )

            backups = []
            for f in results.get("files", []):
                created_raw = f.get("createdTime", "")
                try:
                    created_at = datetime.fromisoformat(
                        created_raw.replace("Z", "+00:00")
                    )
                except ValueError:
                    created_at = datetime.now(timezone.utc)

                backups.append(
                    {
                        "name": f.get("name", ""),
                        "size_bytes": int(f.get("size", 0)),
                        "created_at": created_at,
                        "id": f.get("id", ""),
                    }
                )
            return backups

        except GoogleDriveError:
            raise
        except HttpError as exc:
            log.error("Error listando backups en Drive: %s", exc)
            return []

    async def download_file(self, file_id: str, dest_path: str) -> bool:
        """
        Descarga asíncronamente un archivo desde Google Drive a la ruta local especificada.

        Args:
            file_id: ID del archivo en Google Drive a descargar.
            dest_path: Ruta local donde se almacenará el archivo.

        Returns:
            bool: True si la descarga fue exitosa, False en caso contrario.
        """
        import io
        import asyncio
        from googleapiclient.http import MediaIoBaseDownload

        def _sync_download():
            try:
                service = self._get_service()
                request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
                
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                
                done = False
                log.info("Descargando archivo %s desde Google Drive...", file_id)
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        log.debug("Progreso de descarga: %d%%", int(status.progress() * 100))
                
                fh.seek(0)
                
                # Guardar al disco
                with open(dest_path, "wb") as f:
                    f.write(fh.read())
                    
                log.info("✅ Archivo restaurado con éxito desde Drive en: %s", dest_path)
                return True
                
            except HttpError as exc:
                log.error("Error en la API descargando desde Drive (ID: %s): %s", file_id, exc)
                return False
            except Exception as exc:
                log.error("Error inesperado durante la descarga desde Drive: %s", exc)
                return False

        # Ejecutamos la lógica bloqueante en un hilo separado para no bloquear el event loop de FastAPI
        return await asyncio.to_thread(_sync_download)


    # -------------------------------------------------------------------------
    # Métodos internos de autenticación y construcción del servicio
    # -------------------------------------------------------------------------
    def _get_service(self):
        """
        Devuelve el cliente de la API de Google Drive v3, construyéndolo
        de forma perezosa (lazy) y reutilizándolo entre llamadas.

        Returns:
            Resource: Cliente de la API listo para usar.

        Raises:
            CredentialsNotFoundError: Si no se encuentra ``credentials.json``.
            AuthenticationError:      Si el flujo de autenticación falla.
        """
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def _get_credentials(self) -> Credentials:
        """
        Obtiene o refresca las credenciales de Google.

        Lógica de resolución:
        1. Si ``credentials.json`` es de tipo Service Account, usa ese flujo
           directamente (sin token.json ni interacción de usuario).
        2. Si es OAuth2 Desktop App:
           a. Intenta cargar ``token.json`` (de memoria o de disco).
           b. Si el token expiró y hay refresh_token, lo refresca.
           c. Si no hay token válido, lanza el flujo OAuth2 interactivo.
              El nuevo token se persiste en ``token.json``.

        Returns:
            Credentials: Objeto de credenciales válido.

        Raises:
            CredentialsNotFoundError: Si no hay ``credentials.json``.
            AuthenticationError:      Si falla la autenticación.
        """
        creds_data = self._load_credentials_data()
        cred_type = creds_data.get("type", "")

        # --- Flujo Service Account ---
        if cred_type == "service_account":
            log.debug("Autenticando con Service Account.")
            try:
                creds = service_account.Credentials.from_service_account_info(
                    creds_data, scopes=SCOPES
                )
                return creds
            except (ValueError, KeyError) as exc:
                raise AuthenticationError(
                    f"El archivo credentials.json de Service Account es inválido: {exc}"
                ) from exc

        # --- Flujo OAuth2 Desktop App ---
        log.debug("Autenticando con OAuth2 Desktop App.")
        creds: Credentials | None = None

        # 1. Intentar cargar el token guardado.
        token_data = self._load_token_data()
        if token_data:
            try:
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            except (ValueError, KeyError) as exc:
                log.warning("token.json inválido, se ignorará: %s", exc)
                creds = None

        # 2. Refrescar si expiró pero hay refresh_token.
        if creds and not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    log.debug("Token OAuth2 refrescado correctamente.")
                    self._persist_token(creds)
                except RefreshError as exc:
                    log.warning("No se pudo refrescar el token: %s. Se iniciará flujo OAuth2.", exc)
                    creds = None
            else:
                creds = None

        # 3. Flujo OAuth2 interactivo si no hay token válido.
        if not creds or not creds.valid:
            raise AuthenticationError(
                "La cuenta de Google Drive no está vinculada. Por favor, conéctala desde la interfaz web de SolbaBackups."
            )

        return creds

    def _build_service(self):
        """
        Construye y devuelve el cliente de Google Drive API v3.

        Returns:
            Resource: Cliente de la API.

        Raises:
            CredentialsNotFoundError, AuthenticationError, ConnectionError.
        """
        try:
            creds = self._get_credentials()
            service = build("drive", "v3", credentials=creds, cache_discovery=False)
            log.debug("Servicio de Google Drive API v3 construido.")
            return service
        except GoogleDriveError:
            raise
        except (socket.timeout, socket.error) as exc:
            raise ConnectionError(
                "No hay conectividad con los servidores de Google. Verifica tu red."
            ) from exc
        except Exception as exc:
            raise AuthenticationError(
                f"Error inesperado construyendo el cliente de Drive: {exc}"
            ) from exc

    def _get_or_create_job_folder(self, service) -> str:
        """
        Obtiene o crea la subcarpeta del job dentro de la carpeta configurada.

        Si ``folder_id`` no está configurado, sube a la raíz del Drive del
        usuario autenticado. Dentro, busca (o crea) una carpeta con el nombre
        del job para organizar los backups.

        Args:
            service: Cliente de la API de Google Drive.

        Returns:
            str: ID de la carpeta del job en Google Drive.

        Raises:
            UploadError: Si falla la búsqueda o creación de la carpeta.
        """
        try:
            parent_id = self._folder_id

            # Buscar subcarpeta con nombre del job.
            query_parts = [
                f"name = '{self._job_name}'",
                f"mimeType = '{_FOLDER_MIME}'",
                "trashed = false",
            ]
            if parent_id:
                query_parts.append(f"'{parent_id}' in parents")

            query = " and ".join(query_parts)
            results = (
                service.files()
                .list(q=query, fields="files(id,name)", pageSize=1, supportsAllDrives=True, includeItemsFromAllDrives=True)
                .execute()
            )
            files = results.get("files", [])

            if files:
                folder_id = files[0]["id"]
                log.debug("Carpeta de job encontrada en Drive: %s (id=%s)", self._job_name, folder_id)
                return folder_id

            # Crear la carpeta si no existe.
            folder_metadata: dict[str, Any] = {
                "name": self._job_name,
                "mimeType": _FOLDER_MIME,
            }
            if parent_id:
                folder_metadata["parents"] = [parent_id]

            folder = (
                service.files()
                .create(body=folder_metadata, fields="id", supportsAllDrives=True)
                .execute()
            )
            folder_id = folder["id"]
            log.info("📁 Carpeta de job creada en Drive: %s (id=%s)", self._job_name, folder_id)
            return folder_id

        except HttpError as exc:
            raise UploadError(
                f"Error HTTP creando/obteniendo la carpeta del job '{self._job_name}': "
                f"{exc.resp.status} {exc.reason}"
            ) from exc

    # -------------------------------------------------------------------------
    # Helpers de persistencia de credenciales
    # -------------------------------------------------------------------------
    def _load_credentials_data(self) -> dict:
        """
        Carga el contenido de ``credentials.json`` desde memoria o disco.

        Returns:
            dict: Diccionario con las credenciales.

        Raises:
            CredentialsNotFoundError: Si no se encuentra ni en memoria ni en disco.
        """
        # Prioridad 1: contenido en memoria (pasado en el constructor).
        if self._credentials_json:
            try:
                return json.loads(self._credentials_json)
            except json.JSONDecodeError as exc:
                raise CredentialsNotFoundError(
                    f"El string credentials_json no es JSON válido: {exc}"
                ) from exc

        # Prioridad 2: archivo en disco.
        if not self._credentials_file.exists():
            raise CredentialsNotFoundError(
                f"No se encontró el archivo de credenciales: {self._credentials_file}\n"
                "Descárgalo desde Google Cloud Console → APIs & Services → Credentials."
            )

        try:
            with open(self._credentials_file, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            # Google envuelve las credentials de OAuth2 Desktop en una clave "installed" o "web".
            if "installed" in raw:
                return raw  # InstalledAppFlow lo maneja completo.
            if "web" in raw:
                return raw
            return raw  # Service Account no tiene wrapper.
        except (json.JSONDecodeError, OSError) as exc:
            raise CredentialsNotFoundError(
                f"No se pudo leer '{self._credentials_file}': {exc}"
            ) from exc

    def _load_token_data(self) -> dict | None:
        """
        Carga el token OAuth2 guardado desde memoria o disco.

        Returns:
            dict | None: Datos del token o ``None`` si no existe.
        """
        if self._token_json:
            try:
                return json.loads(self._token_json)
            except json.JSONDecodeError:
                log.warning("token_json en memoria no es JSON válido, se ignora.")
                return None

        if self._token_file.exists():
            try:
                with open(self._token_file, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("No se pudo leer '%s': %s", self._token_file, exc)
        return None

    def _persist_token(self, creds: Credentials) -> None:
        """
        Guarda el token OAuth2 en disco para reutilizarlo en futuras ejecuciones.

        Args:
            creds: Credenciales OAuth2 frescas a persistir.
        """
        try:
            self._token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._token_file, "w", encoding="utf-8") as fh:
                fh.write(creds.to_json())
            log.debug("Token OAuth2 guardado en: %s", self._token_file)
        except OSError as exc:
            log.warning("No se pudo guardar el token en '%s': %s", self._token_file, exc)
