from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from src.api.dependencies import get_db
from src.db.models import Job, LogEntry, RunHistory

router = APIRouter(tags=["Stats"])

@router.get(
    "/stats",
    openapi_extra={
        "responses": {
            "200": {
                "description": "Estadísticas globales",
                "content": {
                    "application/json": {
                        "examples": {
                            "ok": {
                                "value": {
                                    "total_jobs": 3,
                                    "success_rate": 80,
                                    "total_space_mb": 512.34,
                                    "avg_duration_secs": 42.7,
                                    "avg_execution_time_by_job": [
                                        {"job_id": 1, "job_name": "ERP", "avg_duration_secs": 55.2, "runs_count": 12},
                                        {"job_id": 2, "job_name": "CRM", "avg_duration_secs": 31.9, "runs_count": 8},
                                    ],
                                    "runs_last_7_days": [
                                        {"date": "2026-05-06", "success": 1, "failed": 0},
                                        {"date": "2026-05-07", "success": 0, "failed": 1},
                                        {"date": "2026-05-08", "success": 2, "failed": 0},
                                        {"date": "2026-05-09", "success": 1, "failed": 0},
                                        {"date": "2026-05-10", "success": 0, "failed": 0},
                                        {"date": "2026-05-11", "success": 1, "failed": 0},
                                        {"date": "2026-05-12", "success": 0, "failed": 0},
                                    ],
                                }
                            }
                        }
                    }
                },
            }
        }
    },
)
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

    success_runs_data = db.query(
        RunHistory.id,
        RunHistory.job_id,
        RunHistory.started_at,
        RunHistory.finished_at,
    ).filter(
        RunHistory.status == "success",
        RunHistory.started_at.isnot(None),
    ).all()

    avg_execution_time_by_job: list[dict[str, any]] = []
    if success_runs_data:
        run_ids = [r.id for r in success_runs_data]
        done_ts_rows = db.query(
            LogEntry.run_id,
            func.max(LogEntry.timestamp),
        ).filter(
            LogEntry.run_id.in_(run_ids),
            LogEntry.stage == "done",
        ).group_by(LogEntry.run_id).all()
        done_ts_by_run = {rid: ts for rid, ts in done_ts_rows if ts is not None}

        job_ids = sorted({r.job_id for r in success_runs_data})
        job_name_rows = db.query(Job.id, Job.name).filter(Job.id.in_(job_ids)).all()
        job_name_by_id = {jid: name for jid, name in job_name_rows}

        durations_by_job: dict[int, list[float]] = {}
        for r in success_runs_data:
            end_ts = done_ts_by_run.get(r.id) or r.finished_at
            if not end_ts or not r.started_at:
                continue
            duration = (end_ts - r.started_at).total_seconds()
            durations_by_job.setdefault(r.job_id, []).append(duration)

        for job_id, durations in durations_by_job.items():
            if not durations:
                continue
            avg_execution_time_by_job.append(
                {
                    "job_id": job_id,
                    "job_name": job_name_by_id.get(job_id, f"job_{job_id}"),
                    "avg_duration_secs": round(sum(durations) / len(durations), 1),
                    "runs_count": len(durations),
                }
            )
        avg_execution_time_by_job.sort(key=lambda x: x["job_name"].lower())

    return {
        "total_jobs": total_jobs,
        "success_rate": success_rate,
        "total_space_mb": total_space_mb,
        "avg_duration_secs": avg_duration_secs,
        "avg_execution_time_by_job": avg_execution_time_by_job,
        "runs_last_7_days": runs_last_7_days
    }
