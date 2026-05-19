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
from src.api.dependencies import get_db, get_job_manager
from src.core.job_manager import JobManager
from src.core.windows_tasks import create_or_update_windows_task, delete_windows_task

from src.core.discovery import scan_local_databases

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/discovery")
async def get_discovery():
    """
    Escanea localhost asíncronamente y devuelve los motores de BD activos detectados.
    """
    results = await scan_local_databases()
    return results

@router.post("/test-connection")
async def test_job_connection(conn_in: models.JobTestConnection):
    """
    Intenta establecer una conexión rápida a la base de datos o carpeta para verificar que es accesible.
    No guarda la configuración.
    """
    import os
    from pathlib import Path
    
    if conn_in.db_type == "postgresql":
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=conn_in.db_host or "localhost",
                port=conn_in.db_port or 5432,
                user=conn_in.db_user or "",
                password=conn_in.db_password or "",
                dbname=conn_in.db_name or "",
                connect_timeout=3
            )
            conn.close()
            return {"success": True, "message": "Conexión a PostgreSQL establecida con éxito."}
        except Exception as e:
            raise HTTPException(status_code=400, detail="No se pudo conectar a PostgreSQL. Revisa host/puerto/usuario/contraseña y que el servidor esté accesible.")
            
    elif conn_in.db_type == "mysql":
        try:
            import pymysql
            conn = pymysql.connect(
                host=conn_in.db_host or "localhost",
                port=conn_in.db_port or 3306,
                user=conn_in.db_user or "",
                password=conn_in.db_password or "",
                database=conn_in.db_name or "",
                connect_timeout=3
            )
            conn.close()
            return {"success": True, "message": "Conexión a MySQL/MariaDB establecida con éxito."}
        except Exception as e:
            raise HTTPException(status_code=400, detail="No se pudo conectar a MySQL/MariaDB. Revisa host/puerto/usuario/contraseña y que el servidor esté accesible.")
            
    elif conn_in.db_type == "sqlserver":
        try:
            import subprocess
            host_str = f"{conn_in.db_host},{conn_in.db_port}" if conn_in.db_port else f"{conn_in.db_host}"
            cmd = ["sqlcmd", "-S", host_str, "-U", conn_in.db_user or "", "-P", conn_in.db_password or "", "-d", conn_in.db_name or "master", "-Q", "SELECT 1", "-t", "3"]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if process.returncode != 0:
                raise Exception(process.stderr or process.stdout)
            return {"success": True, "message": "Conexión a SQL Server (sqlcmd) establecida con éxito."}
        except Exception as e:
            raise HTTPException(status_code=400, detail="No se pudo conectar a SQL Server. Revisa host/puerto/usuario/contraseña y que el servidor esté accesible.")
            
    elif conn_in.db_type in ["sqlite", "mdb", "folder"]:
        if not conn_in.db_name:
            raise HTTPException(status_code=400, detail="Debe especificar una ruta válida.")
        path = Path(conn_in.db_name)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"La ruta especificada no existe: {conn_in.db_name}")
        
        if conn_in.db_type == "folder" and not path.is_dir():
            raise HTTPException(status_code=400, detail="La ruta debe apuntar a un directorio/carpeta.")
        elif conn_in.db_type in ["sqlite", "mdb"] and not path.is_file():
            raise HTTPException(status_code=400, detail="La ruta debe apuntar a un archivo válido.")
            
        return {"success": True, "message": f"Ruta accesible ({conn_in.db_type})."}
        
    else:
        raise HTTPException(status_code=400, detail=f"Tipo de motor no soportado para test: {conn_in.db_type}")


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
):
    """
    Crea un nuevo Job de backup y lo programa automáticamente si tiene schedule.
    """
    existing_job = crud.job_get_by_name(db, name=job_in.name)
    if existing_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una tarea con el nombre '{job_in.name}'. Por favor, elige otro.",
        )

    job_data = job_in.model_dump(exclude_unset=True)
    new_job = crud.job_create(db, job_data)

    # Registrar en el scheduler de Windows si tiene schedule automático
    if new_job.schedule_type and new_job.schedule_type.lower() not in (
        "manual",
        "none",
        "",
    ):
        create_or_update_windows_task(new_job)

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
                detail=f"Ya existe una tarea con el nombre '{job_in.name}'. Por favor, elige otro.",
            )

    job_data = job_in.model_dump(exclude_unset=True)
    if not job_in.db_password:
        job_data.pop("db_password", None)
    updated_job = crud.job_update(db, job_id, job_data)

    # Reprogramar en tiempo real en Windows
    if updated_job and updated_job.schedule_type and updated_job.schedule_type.lower() not in (  # type: ignore
        "manual",
        "none",
        "",
    ):
        create_or_update_windows_task(updated_job)
    else:
        delete_windows_task(job_id)  # Si el usuario quitó el schedule, cancelar

    return updated_job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
):
    """
    Elimina un Job, su historial y lo desprograma del scheduler de Windows.
    """
    delete_windows_task(job_id)  # Cancelar si estaba programado en Windows
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
