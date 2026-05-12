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

    # Tiempo promedio de ejecución
    avg_duration = db.query(func.avg(RunHistory.duration_secs)).filter(
        RunHistory.duration_secs.isnot(None)
    ).scalar() or 0
    avg_duration_secs = round(avg_duration, 1)

    # Últimos 7 días (agrupado por fecha y estado)
    from datetime import datetime, timedelta, timezone
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Esto es una query unificada, pero la adaptamos para SQLite/Postgres de forma genérica
    # extrayendo los datos y agrupándolos en memoria si no queremos pelear con dialectos SQL
    recent_runs = db.query(RunHistory.started_at, RunHistory.status).filter(
        RunHistory.started_at >= seven_days_ago
    ).all()
    
    # Inicializar últimos 7 días con tipado flexible
    days_data: dict[str, dict[str, any]] = {}
    for i in range(7):
        d = (datetime.now(timezone.utc) - timedelta(days=6-i)).strftime("%Y-%m-%d")
        days_data[d] = {"date": d, "success": 0, "failed": 0}
        
    for run_start, status in recent_runs:
        if run_start:
            day_str = run_start.strftime("%Y-%m-%d")
            if day_str in days_data:
                if status == 'success':
                    days_data[day_str]["success"] += 1
                else:
                    days_data[day_str]["failed"] += 1
                    
    runs_last_7_days = list(days_data.values())

    return {
        "total_jobs": total_jobs,
        "success_rate": success_rate,
        "total_space_mb": total_space_mb,
        "avg_duration_secs": avg_duration_secs,
        "runs_last_7_days": runs_last_7_days
    }
