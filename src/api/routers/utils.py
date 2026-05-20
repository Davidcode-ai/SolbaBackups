import json
import os
import shutil
import socket
import string
import sys
from pathlib import Path

# Ruta base compatible con modo frozen (PyInstaller) y modo script
if getattr(sys, 'frozen', False):
    _GDRIVE_BASE_DIR = Path(sys.executable).parent
else:
    _GDRIVE_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.db import crud

router = APIRouter(prefix="/utils", tags=["Utils"])


class TestDbRequest(BaseModel):
    """Payload para probar conexión o listar bases de datos."""

    host: str = Field(..., min_length=1, examples=["localhost"])
    port: int = Field(..., ge=1, le=65535, examples=[5432])
    user: str = Field(..., min_length=1, examples=["postgres"])
    password: str = Field(default="", examples=["secret"])
    engine: str = Field(..., min_length=1, examples=["postgresql"])
    database: str = Field(default="", examples=["postgres"])
    job_id: int | None = Field(
        default=None,
        ge=1,
        description="Si la contraseña viene vacía en modo edición, se usa la del job.",
    )


# Alias retrocompatible con el nombre anterior del esquema.
TestConnectionRequest = TestDbRequest


def _resolve_db_password(
    password: str | None,
    job_id: int | None,
    db: Session,
) -> str:
    """
    Devuelve la contraseña del payload o, si está vacía, la guardada en el job.
    Nunca registra la contraseña en logs.
    """
    plain = (password or "").strip()
    if plain:
        return plain

    if job_id is None:
        return ""

    job = crud.job_get_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    stored = getattr(job, "db_password", None)
    if stored and str(stored).strip():
        return str(stored).strip()

    enc = getattr(job, "db_password_enc", None)
    if enc and str(enc).strip():
        try:
            from src.config.settings import Settings
            from src.processors.encryptor import Encryptor

            settings = Settings()
            key_raw = (settings._config.get("encryption_key") or "").strip()
            if key_raw:
                decrypted = Encryptor.decrypt_field(str(enc).strip(), key_raw.encode("utf-8"))
                if decrypted and str(decrypted).strip():
                    return str(decrypted).strip()
        except Exception:
            pass

    return ""


@router.post(
    "/test-connection",
    summary="Probar conexión (host:puerto o real para DB)",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "postgres": {
                            "summary": "PostgreSQL",
                            "value": {
                                "host": "localhost",
                                "port": 5432,
                                "user": "postgres",
                                "password": "secret",
                                "engine": "postgresql",
                                "database": "postgres",
                            },
                        }
                    }
                }
            }
        },
        "responses": {
            "200": {
                "description": "OK",
                "content": {
                    "application/json": {
                        "examples": {
                            "ok": {
                                "value": {
                                    "success": True,
                                    "message": "Conexión establecida correctamente.",
                                }
                            }
                        }
                    }
                },
            },
            "400": {
                "description": "No alcanzable / error de conexión",
                "content": {
                    "application/json": {
                        "examples": {
                            "refused": {
                                "value": {
                                    "detail": "No se pudo conectar: Error de credenciales o red"
                                }
                            }
                        }
                    }
                },
            },
        },
    },
)
def test_connection(
    payload: TestDbRequest,
    db: Session = Depends(get_db),
) -> dict:
    password = _resolve_db_password(payload.password, payload.job_id, db)

    if payload.engine.lower() == "postgresql":
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=payload.host,
                port=payload.port,
                user=payload.user,
                password=password,
                dbname=payload.database or "postgres",
                connect_timeout=5
            )
            conn.close()
            return {"success": True, "message": "Conexión a PostgreSQL establecida correctamente."}
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Error de autenticación: Verifica tu usuario y contraseña.")
        except Exception as e:
            # Usamos repr() para evitar el crash al evaluar caracteres especiales
            error_msg = repr(e)
            if 'password' in error_msg.lower() or 'autentica' in error_msg.lower() or 'FATAL' in error_msg:
                raise HTTPException(status_code=400, detail="Contraseña incorrecta o usuario no válido.")
            raise HTTPException(status_code=400, detail="No se pudo conectar a la base de datos con los datos proporcionados.")

    # Fallback genérico a conexión TCP
    try:
        with socket.create_connection((payload.host, payload.port), timeout=3):
            return {"success": True, "message": "Conexión TCP establecida correctamente."}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo conectar al puerto TCP {payload.port} en {payload.host}. Error: {e}",
        )

@router.post("/test-db")
def list_databases(
    payload: TestDbRequest,
    db: Session = Depends(get_db),
) -> dict:
    password = _resolve_db_password(payload.password, payload.job_id, db)
    engine = payload.engine.lower()
    databases = []
    
    try:
        if engine == "postgresql":
            import psycopg2
            conn = psycopg2.connect(
                host=payload.host,
                port=payload.port,
                user=payload.user,
                password=password,
                dbname=payload.database or "postgres",
                connect_timeout=5
            )
            cur = conn.cursor()
            cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
            databases = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
            
        elif engine == "mysql":
            import pymysql
            conn = pymysql.connect(
                host=payload.host,
                port=payload.port,
                user=payload.user,
                password=password,
                database=payload.database or None,
                connect_timeout=5
            )
            cur = conn.cursor()
            cur.execute("SHOW DATABASES;")
            databases = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
            
        elif engine == "sqlserver":
            import subprocess
            host_str = f"{payload.host},{payload.port}" if payload.port else payload.host
            cmd = ["sqlcmd", "-S", host_str, "-U", payload.user, "-P", password, "-Q", "SET NOCOUNT ON; SELECT name FROM master.dbo.sysdatabases;", "-h", "-1"]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if process.returncode != 0:
                raise Exception(process.stderr or process.stdout)
            
            # sqlcmd devuelve las db separadas por saltos de linea
            lines = process.stdout.split('\n')
            databases = [line.strip() for line in lines if line.strip() and not line.startswith('-')]
            
        else:
            raise HTTPException(status_code=400, detail=f"Listar bases de datos no soportado para el motor {engine}.")
            
    except ImportError as e:
        raise HTTPException(status_code=400, detail=f"Librería requerida no encontrada para {engine}: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al listar bases de datos: {repr(e)}")
        
    return {"databases": databases}

@router.get("/drives")
def get_drives():
    """Devuelve los discos disponibles en el sistema."""
    drives = []
    if os.name == 'nt':
        # Windows
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
    else:
        # Unix/Linux/Mac
        drives.append("/")
    return {"drives": drives}

@router.get("/list-dir")
def list_dir(path: str = ""):
    """Devuelve el contenido de un directorio (carpetas y archivos)."""
    if not path:
        if os.name == 'nt':
            return {"folders": [{"name": d, "path": d} for d in get_drives()["drives"]], "files": []}
        else:
            path = "/"
            
    p = Path(path)
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=404, detail="Directorio no encontrado")
        
    try:
        folders = []
        files = []
        for item in p.iterdir():
            try:
                if item.is_dir():
                    folders.append({"name": item.name, "path": str(item)})
                else:
                    files.append({"name": item.name, "path": str(item)})
            except PermissionError:
                pass # Ignorar archivos protegidos
        
        # Ordenar alfabéticamente
        folders.sort(key=lambda x: x["name"].lower())
        files.sort(key=lambda x: x["name"].lower())
        
        # Determinar el padre
        parent = str(p.parent) if str(p.parent) != str(p) else None
        
        return {
            "current_path": str(p),
            "parent_path": parent,
            "folders": folders,
            "files": files
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permiso denegado para leer este directorio")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/free-space")
def get_free_space(path: str):
    """Devuelve el espacio libre en MB de un directorio dado."""
    try:
        if not os.path.exists(path):
            # Si la ruta exacta no existe, buscar el disco base
            p = Path(path)
            while not p.exists() and p.parent != p:
                p = p.parent
            path = str(p)
            
        usage = shutil.disk_usage(path)
        free_mb = round(usage.free / (1024 * 1024), 2)
        total_mb = round(usage.total / (1024 * 1024), 2)
        return {
            "path_checked": path,
            "free_space_mb": free_mb,
            "total_space_mb": total_mb
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gdrive-space")
def get_gdrive_space():
    """Devuelve el espacio libre en MB de Google Drive."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GRequest
        from googleapiclient.discovery import build
        
        _DEFAULT_TOKEN_PATH = _GDRIVE_BASE_DIR / "token.json"
        
        if not _DEFAULT_TOKEN_PATH.exists():
            raise HTTPException(status_code=401, detail="Google Drive no está vinculado.")
            
        with open(_DEFAULT_TOKEN_PATH, 'r') as f:
            creds_data = json.load(f)
            
        creds = Credentials.from_authorized_user_info(creds_data, ["https://www.googleapis.com/auth/drive.file"])
        
        if creds.expired and creds.refresh_token:
            creds.refresh(GRequest())
            creds_dict = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }
            with open(_DEFAULT_TOKEN_PATH, 'w') as f:
                json.dump(creds_dict, f)
                
        service = build('drive', 'v3', credentials=creds)
        about = service.about().get(fields='storageQuota').execute()
        quota = about.get('storageQuota', {})
        
        limit = int(quota.get('limit', 0))
        usage = int(quota.get('usage', 0))
        
        if limit == 0:
            free_mb = 0
        else:
            free_mb = round((limit - usage) / (1024 * 1024), 2)
            
        return {"free_space_mb": free_mb}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CreateFolderRequest(BaseModel):
    folder_name: str


class CreateLocalDirRequest(BaseModel):
    parent_path: str = Field(..., min_length=1)
    folder_name: str = Field(..., min_length=1)


@router.post("/create-local-dir")
def create_local_dir(payload: CreateLocalDirRequest):
    """Crea una carpeta en el sistema de archivos local."""
    folder_name = payload.folder_name.strip()
    if not folder_name or folder_name in (".", ".."):
        raise HTTPException(status_code=400, detail="Nombre de carpeta no válido")
    if any(sep in folder_name for sep in ("/", "\\", ":")):
        raise HTTPException(status_code=400, detail="El nombre de carpeta no puede contener separadores de ruta")

    parent = Path(payload.parent_path.strip())
    if not parent.exists() or not parent.is_dir():
        raise HTTPException(status_code=404, detail="Directorio padre no encontrado")

    new_dir = parent / folder_name
    if new_dir.exists():
        raise HTTPException(status_code=409, detail="La carpeta ya existe")

    try:
        os.makedirs(new_dir, exist_ok=False)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permiso denegado para crear la carpeta")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"path": str(new_dir), "name": folder_name}


@router.post("/gdrive-create-folder")
def create_gdrive_folder(payload: CreateFolderRequest):
    """Crea una carpeta en Google Drive y devuelve su ID y nombre."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GRequest
        from googleapiclient.discovery import build
        
        _DEFAULT_TOKEN_PATH = _GDRIVE_BASE_DIR / "token.json"
        
        if not _DEFAULT_TOKEN_PATH.exists():
            raise HTTPException(status_code=401, detail="Google Drive no está vinculado.")
            
        with open(_DEFAULT_TOKEN_PATH, 'r') as f:
            creds_data = json.load(f)
            
        creds = Credentials.from_authorized_user_info(creds_data, ["https://www.googleapis.com/auth/drive.file"])
        
        if creds.expired and creds.refresh_token:
            creds.refresh(GRequest())
            creds_dict = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }
            with open(_DEFAULT_TOKEN_PATH, 'w') as f:
                json.dump(creds_dict, f)
                
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {
            'name': payload.folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        folder = service.files().create(body=file_metadata, fields='id, name').execute()
        return {"id": folder.get("id"), "name": folder.get("name")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
