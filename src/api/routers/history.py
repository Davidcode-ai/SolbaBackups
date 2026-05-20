"""
src/api/routers/history.py — Router de Historial de Ejecuciones.

Proporciona endpoints para consultar el registro histórico de todas las
ejecuciones de backup que se han realizado (tanto programadas como manuales).

Prefijo del router : /api/v1/history
Tag OpenAPI        : History

Endpoints:
    GET /                      → Historial paginado de todas las ejecuciones.
    GET /job/{job_id}          → Historial de las ejecuciones de un job concreto.
    GET /run/{run_id}          → Detalle completo de una ejecución específica.
    DELETE /run/{run_id}       → Eliminar el registro de una ejecución y sus logs.
    GET /run/{run_id}/logs     → Logs detallados de una ejecución.
    POST /restore/{run_id}     → Restaurar backup de una ejecución exitosa.

Modelo de datos de una ejecución (RunHistory):
    - run_id       : ID único de la ejecución.
    - job_id       : ID del job que originó la ejecución.
    - job_name     : Nombre del job (desnormalizado para evitar JOINs en UI).
    - started_at   : Timestamp de inicio.
    - finished_at  : Timestamp de fin (null si en curso).
    - status       : 'running' | 'success' | 'failed' | 'warning'.
    - duration_secs: Duración en segundos.
    - file_size_bytes: Tamaño del archivo de backup producido.
    - destination  : Destino al que se subió.
    - error_message: Mensaje de error si ``status == 'failed'``.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.core.job_manager import JobManager
from src.core.models import RunHistoryRead, LogEntryRead
from src.db import crud

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/history",
    tags=["History"],
)


@router.get(
    "",
    response_model=list[RunHistoryRead],
    summary="Historial paginado de todas las ejecuciones",
)
def list_history(
    page: int = Query(default=1, ge=1, description="Página (empieza en 1)"),
    page_size: int = Query(default=25, ge=1, le=100, description="Registros por página"),
    status_filter: str | None = Query(default=None, alias="status", description="Filtrar por estado"),
    db: Session = Depends(get_db),
) -> list[RunHistoryRead]:
    """
    Devuelve el historial paginado de todas las ejecuciones de todos los jobs.

    Ordenado por ``started_at`` descendente (la más reciente primero).

    Args:
        page:          Número de página (1-indexed).
        page_size:     Número de registros por página (máximo 100).
        status_filter: Filtro opcional por estado de la ejecución.
        db:            Sesión de BD.

    Returns:
        list[RunHistoryRead]: Página de registros de ejecución.
    """
    runs = crud.run_get_all(db, page=page, page_size=page_size, status_filter=status_filter)
    log.info(f"LIST_HISTORY: Devolviendo {len(runs)} runs. IDs: {[r.id for r in runs]}")
    return runs


@router.get(
    "/job/{job_id}",
    response_model=list[RunHistoryRead],
    summary="Historial de ejecuciones de un Job específico",
)
def list_job_history(
    job_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[RunHistoryRead]:
    """
    Devuelve el historial paginado de un job concreto.

    Args:
        job_id:    ID del job.
        page:      Número de página.
        page_size: Registros por página.
        db:        Sesión de BD.

    Returns:
        list[RunHistoryRead]: Ejecuciones del job, más reciente primero.

    Raises:
        HTTPException 404: Si el job no existe.
    """
    # Comprobar si el job existe primero (opcional, pero buena práctica si se exige el 404 documentado)
    job = crud.job_get_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado.")
    return crud.run_get_by_job(db, job_id=job_id, page=page, page_size=page_size)


@router.post(
    "/restore/{run_id}",
    summary="Restaurar backup de una ejecución exitosa",
)
def restore_run_backup(
    run_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Trigger in-process restore for a **successful** run.

    Args:
        run_id: Execution id whose ``backup_file_path`` will be restored.
        db: Database session.

    Returns:
        Result dict from :meth:`~src.core.job_manager.JobManager.restore_backup`.

    Raises:
        HTTPException: 404 if run missing; 409 if status is not ``success``;
            400/404/501/500 wrapping ``ValueError``, ``FileNotFoundError``,
            ``NotImplementedError``, and ``RuntimeError`` from the core layer.
    """
    log.info(f"RESTORE: Intentando restaurar run_id={run_id}")
    
    # Debug: Listar todos los runs disponibles
    all_runs = crud.run_get_all(db, page=1, page_size=100)
    log.info(f"RESTORE: Runs disponibles en BD: {[r.id for r in all_runs]}")
    
    run = crud.run_get_by_id(db, run_id)
    if not run:
        log.error(f"RESTORE: Run {run_id} no encontrado en la base de datos")
        raise HTTPException(status_code=404, detail=f"Ejecución con ID {run_id} no encontrada en la base de datos.")
    
    log.info(f"RESTORE: Run {run_id} encontrado, status={run.status}")
    if (run.status or "").lower() != "success":
        raise HTTPException(
            status_code=409,
            detail=f"Solo se puede restaurar una ejecución SUCCESS. Run {run_id} tiene estado: {run.status}",
        )

    jm = JobManager()
    try:
        return jm.restore_backup(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/run/{run_id}",
    response_model=RunHistoryRead,
    summary="Detalle de una ejecución concreta",
)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> RunHistoryRead:
    """
    Devuelve todos los metadatos de una ejecución específica por su ID.

    Args:
        run_id: ID único de la ejecución.
        db:     Sesión de BD.

    Returns:
        RunHistoryRead: Detalle completo de la ejecución.

    Raises:
        HTTPException 404: Si la ejecución no existe.
    """
    run = crud.run_get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada.")
    return run


@router.delete(
    "/run/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar el registro de una ejecución",
)
def delete_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> None:
    """
    Elimina el registro de una ejecución y todos sus logs asociados.

    Útil para limpiar el historial de ejecuciones fallidas antiguas.

    Args:
        run_id: ID de la ejecución a eliminar.
        db:     Sesión de BD.

    Raises:
        HTTPException 404: Si la ejecución no existe.
        HTTPException 409: Si la ejecución está actualmente en curso (status='running').
    """
    # Validar si está running
    run = crud.run_get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada.")
    if run.status == "running":
        raise HTTPException(status_code=409, detail="No se puede eliminar una ejecución en curso.")
        
    crud.run_delete(db, run_id)
    return None


@router.get(
    "/run/{run_id}/logs",
    summary="Logs detallados de una ejecución",
)
def get_run_logs(
    run_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Devuelve todas las entradas de log de una ejecución en formato legible
    para el visor de terminal del frontend.

    Devuelve un objeto ``{"logs": [...]}`` donde cada elemento es una línea
    formateada: ``[HH:MM:SS] [LEVEL] mensaje``.

    Raises:
        HTTPException 404: Si la ejecución no existe.
    """
    run = crud.run_get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada.")

    entries = crud.log_get_by_run(db, run_id)

    if not entries:
        # Devolver un log mínimo con el estado final del run
        return {"logs": [f"[INFO] La ejecución finalizó con estado: {run.status.upper()}. No hay entradas de log detalladas."]}

    # Formatear cada entrada con fecha y hora real del evento:
    # [YYYY-MM-DD HH:MM:SS] [LEVEL] stage: mensaje
    lines = []
    for entry in entries:
        time_str = (
            entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if entry.timestamp
            else "????-??-?? ??:??:??"
        )
        lines.append(f"[{time_str}] [{entry.level}] {entry.stage}: {entry.message}")

    return {"logs": lines}


@router.get(
    "/run/{run_id}/download",
    summary="Descargar el backup asociado a un run",
    openapi_extra={
        "responses": {
            "200": {
                "description": "Archivo local o JSON con URL de descarga (Google Drive).",
                "content": {
                    "application/json": {
                        "examples": {
                            "google_drive": {
                                "summary": "Backup en Google Drive",
                                "value": {
                                    "run_id": 123,
                                    "provider": "google_drive",
                                    "download_url": "https://drive.google.com/uc?export=download&id=FILE_ID",
                                    "view_url": "https://drive.google.com/file/d/FILE_ID/view",
                                },
                            }
                        }
                    }
                },
            },
            "400": {
                "description": "Ruta/URL inválida",
                "content": {
                    "application/json": {
                        "examples": {
                            "invalid_gdrive_url": {
                                "value": {"detail": "No se pudo extraer el file_id de la URL de Google Drive."}
                            }
                        }
                    }
                },
            },
            "404": {
                "description": "Run o archivo no encontrado",
                "content": {
                    "application/json": {
                        "examples": {
                            "run_not_found": {"value": {"detail": "Ejecución no encontrada."}},
                            "file_not_found": {"value": {"detail": "No se encontró el archivo de backup en disco."}},
                        }
                    }
                },
            },
        }
    },
)
def download_run_backup(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Return a local backup file, a ZIP of a backup directory, or Drive URLs.

    If ``backup_file_path`` points to Google Drive, responds with JSON
    containing ``download_url`` and ``view_url``. Local files use
    :class:`~fastapi.responses.FileResponse`; local directories are zipped
    into a temp folder and streamed with a background cleanup task.

    Args:
        run_id: Run whose artifact path should be served.
        db: Database session.

    Returns:
        ``FileResponse``, a JSON dict for Drive, or error payload.

    Raises:
        HTTPException: 404 if run or path missing; 400 for unsupported remote
            schemes or bad Drive URLs; 500 if zipping a directory fails.
    """
    run = crud.run_get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada.")

    backup_file_path = (run.backup_file_path or "").strip()
    if not backup_file_path:
        backup_file_path = (run.destination_url or "").strip()
    if not backup_file_path:
        raise HTTPException(
            status_code=404,
            detail="La ejecución no tiene ruta de backup almacenada (backup_file_path).",
        )

    if backup_file_path.startswith("https://drive.google.com"):
        if "/d/" not in backup_file_path:
            raise HTTPException(
                status_code=400,
                detail="No se pudo extraer el file_id de la URL de Google Drive.",
            )
        file_id = backup_file_path.split("/d/")[1].split("/")[0]
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        return {
            "run_id": run_id,
            "provider": "google_drive",
            "download_url": download_url,
            "view_url": backup_file_path,
        }

    if backup_file_path.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400,
            detail="Este backup está en un destino remoto; no hay archivo local para descargar.",
        )

    path = Path(backup_file_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró el artefacto de backup en disco: {path}",
        )

    if path.is_file():
        return FileResponse(
            path=str(path),
            filename=path.name,
            media_type="application/octet-stream",
        )

    if path.is_dir():
        tmpdir = tempfile.mkdtemp(prefix="solba_history_dl_")
        base_name = os.path.join(tmpdir, "backup_bundle")
        try:
            archive_path = shutil.make_archive(base_name, "zip", root_dir=str(path))
        except OSError as exc:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise HTTPException(
                status_code=500,
                detail=f"No se pudo comprimir la carpeta para descarga: {exc}",
            ) from exc

        def cleanup_zip_dir() -> None:
            shutil.rmtree(tmpdir, ignore_errors=True)

        zip_filename = f"{path.name}.zip"
        return FileResponse(
            path=archive_path,
            filename=zip_filename,
            media_type="application/zip",
            background=BackgroundTask(cleanup_zip_dir),
        )

    raise HTTPException(
        status_code=400,
        detail="La ruta de backup no es un archivo ni un directorio válido.",
    )
