import os
import shutil
import socket
import string
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/utils", tags=["Utils"])

class TestConnectionRequest(BaseModel):
    host: str = Field(..., min_length=1, examples=["localhost"])
    port: int = Field(..., ge=1, le=65535, examples=[5432])
    user: str = Field(..., min_length=1, examples=["postgres"])
    password: str = Field(..., min_length=1, examples=["secret"])
    engine: str = Field(..., min_length=1, examples=["postgresql"])


@router.post(
    "/test-connection",
    summary="Probar conexión (host:puerto)",
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
                                    "message": "Conexión TCP establecida correctamente.",
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
                                    "detail": "No se pudo conectar: [Errno 111] Connection refused"
                                }
                            }
                        }
                    }
                },
            },
        },
    },
)
def test_connection(payload: TestConnectionRequest) -> dict:
    try:
        with socket.create_connection((payload.host, payload.port), timeout=3):
            return {"success": True, "message": "Conexión TCP establecida correctamente."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo conectar: {str(e)}")


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
