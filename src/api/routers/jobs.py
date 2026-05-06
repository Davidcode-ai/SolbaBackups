"""
src/api/routers/jobs.py — Endpoints para gestión de Jobs.

Expone las operaciones CRUD sobre la entidad Job mediante una API REST.
La validación de entrada/salida la realiza Pydantic usando los modelos
de ``src.core.models``.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core import models
from src.db import crud
from src.db.database import get_db

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=list[models.JobRead])
def list_jobs(db: Session = Depends(get_db)):
    """
    Lista todos los Jobs configurados en el sistema.
    """
    jobs = crud.job_get_all(db)
    return jobs


@router.post("", response_model=models.JobRead, status_code=status.HTTP_201_CREATED)
def create_job(job_in: models.JobCreate, db: Session = Depends(get_db)):
    """
    Crea un nuevo Job de backup.
    
    Verifica que el nombre sea único antes de delegar la creación al CRUD.
    """
    existing_job = crud.job_get_by_name(db, name=job_in.name)
    if existing_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un Job con ese nombre."
        )
    
    # Extraemos el diccionario del modelo Pydantic para pasarlo al CRUD
    job_data = job_in.model_dump(exclude_unset=True)
    new_job = crud.job_create(db, job_data)
    
    return new_job


@router.get("/{job_id}", response_model=models.JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """
    Obtiene el detalle completo de un Job específico.
    """
    job = crud.job_get_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job no encontrado."
        )
    return job


@router.put("/{job_id}", response_model=models.JobRead)
def update_job(job_id: int, job_in: models.JobUpdate, db: Session = Depends(get_db)):
    """
    Actualiza la configuración de un Job existente de forma parcial.
    Solo se actualizan los campos enviados en el payload.
    """
    job = crud.job_get_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job no encontrado."
        )
        
    # Verificar colisión de nombres si se está cambiando el nombre
    if job_in.name and job_in.name != job.name:
        existing = crud.job_get_by_name(db, name=job_in.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe otro Job con ese nombre."
            )
            
    job_data = job_in.model_dump(exclude_unset=True)
    updated_job = crud.job_update(db, job_id, job_data)
    
    return updated_job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """
    Elimina un Job y todo su historial de ejecuciones asociadas.
    """
    success = crud.job_delete(db, job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job no encontrado."
        )
    # 204 No Content no devuelve body
    return None
