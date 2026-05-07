"""
src/api/routers/history.py — Router de Historial de Ejecuciones.

Proporciona endpoints para consultar el registro histórico de todas las
ejecuciones de backup que se han realizado (tanto programadas como manuales).

Prefijo del router : /api/v1/history
Tag OpenAPI        : History

Endpoints:
    GET /              → Historial paginado de todas las ejecuciones.
    GET /{job_id}      → Historial de las ejecuciones de un job concreto.
    GET /run/{run_id}  → Detalle completo de una ejecución específica.
    DELETE /run/{run_id} → Eliminar el registro de una ejecución y sus logs.

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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.core.models import RunHistoryRead
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
    return crud.run_get_all(db, page=page, page_size=page_size, status_filter=status_filter)


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
