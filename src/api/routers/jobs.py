"""
src/api/routers/jobs.py — Endpoints para gestión de Jobs.

Expone las operaciones CRUD sobre la entidad Job mediante una API REST.
La validación de entrada/salida la realiza Pydantic usando los modelos
de ``src.core.models``.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from src.core import models
from src.db import crud
from src.api.dependencies import get_db, get_job_manager, get_scheduler
from src.core.job_manager import JobManager
from src.core.job_scheduler import JobScheduler

from src.core.discovery import scan_local_databases

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/discovery")
async def get_discovery():
    """
    Escanea localhost asíncronamente y devuelve los motores de BD activos detectados.
    """
    results = await scan_local_databases()
    return results


@router.get("", response_model=list[models.JobRead])
def list_jobs(db: Session = Depends(get_db)):
    """
    Lista todos los Jobs configurados en el sistema.
    """
    jobs = crud.job_get_all(db)
    return jobs


@router.post("", response_model=models.JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    job_in: models.JobCreate,
    db: Session = Depends(get_db),
    scheduler: JobScheduler = Depends(get_scheduler),
):
    """
    Crea un nuevo Job de backup y lo programa automáticamente si tiene schedule.
    """
    existing_job = crud.job_get_by_name(db, name=job_in.name)
    if existing_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un Job con ese nombre.",
        )

    job_data = job_in.model_dump(exclude_unset=True)
    new_job = crud.job_create(db, job_data)

    # Registrar en el scheduler si tiene schedule automático
    if new_job.schedule_type and new_job.schedule_type.lower() not in (
        "manual",
        "none",
        "",
    ):
        scheduler.add_job(new_job)

    return new_job


@router.get("/{job_id}", response_model=models.JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """
    Obtiene el detalle completo de un Job específico.
    """
    job = crud.job_get_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado."
        )
    return job


@router.put("/{job_id}", response_model=models.JobRead)
def update_job(
    job_id: int,
    job_in: models.JobUpdate,
    db: Session = Depends(get_db),
    scheduler: JobScheduler = Depends(get_scheduler),
):
    """
    Actualiza la configuración de un Job y reprograma su schedule si cambió.
    """
    job = crud.job_get_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado."
        )

    if job_in.name and job_in.name != job.name:
        existing = crud.job_get_by_name(db, name=job_in.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe otro Job con ese nombre.",
            )

    job_data = job_in.model_dump(exclude_unset=True)
    updated_job = crud.job_update(db, job_id, job_data)

    # Reprogramar en tiempo real (remove + add con la nueva config)
    if updated_job.schedule_type and updated_job.schedule_type.lower() not in (
        "manual",
        "none",
        "",
    ):
        scheduler.add_job(updated_job)  # add_job ya hace remove internamente
    else:
        scheduler.remove_job(job_id)  # Si el usuario quitó el schedule, cancelar

    return updated_job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    scheduler: JobScheduler = Depends(get_scheduler),
):
    """
    Elimina un Job, su historial y lo desprograma del scheduler.
    """
    scheduler.remove_job(job_id)  # Cancelar si estaba programado
    success = crud.job_delete(db, job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado."
        )
    return None


@router.post("/{job_id}/run")
async def run_job_manually(
    job_id: int,
    db: Session = Depends(get_db),
    manager: JobManager = Depends(get_job_manager),
):
    """
    Ejecuta un Job manualmente bajo demanda.
    Nota: Al usar `await`, la respuesta HTTP esperará a que el backup termine.
    """
    job = crud.job_get_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado."
        )

    # Inicia la ejecución síncrona/esperada
    await manager.run_job(job_id, trigger="manual")

    return {"message": f"Backup del Job {job_id} en ejecución"}
