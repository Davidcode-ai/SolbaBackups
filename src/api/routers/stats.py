from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from src.api.dependencies import get_db
from src.db.models import Job, RunHistory

router = APIRouter(tags=["Stats"])

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    # total_jobs: Conteo total de jobs configurados
    total_jobs = db.query(Job).count()

    # Total de ejecuciones
    total_runs = db.query(RunHistory).count()

    # Ejecuciones con status == 'success'
    success_runs = db.query(RunHistory).filter(RunHistory.status == 'success').count()

    # success_rate
    if total_runs > 0:
        success_rate = round((success_runs / total_runs) * 100)
    else:
        success_rate = 0

    # total_space_mb: Suma del campo file_size_bytes de todas las ejecuciones 'success'
    total_space_bytes = db.query(func.sum(RunHistory.file_size_bytes)).filter(
        RunHistory.status == 'success',
        RunHistory.file_size_bytes.isnot(None)
    ).scalar() or 0

    total_space_mb = round(total_space_bytes / (1024 * 1024), 2)

    return {
        "total_jobs": total_jobs,
        "success_rate": success_rate,
        "total_space_mb": total_space_mb
    }
