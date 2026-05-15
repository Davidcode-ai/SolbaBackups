"""
app/core/scheduler.py  –  Configuración y ciclo de vida del APScheduler.

El scheduler arranca junto con el servidor FastAPI (via lifespan) y se detiene
de forma ordenada cuando el servidor se apaga.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import AsyncSessionLocal
from app.worker import process_pending_notifications
from app.sweeper import recover_orphaned_notifications

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Jobs: wrappers con manejo de errores
# ---------------------------------------------------------------------------
import asyncio

async def _job_worker() -> None:
    """Lee notificaciones PENDING y las envía vía Meta Cloud API."""
    try:
        async with AsyncSessionLocal() as session:
            await process_pending_notifications(session)
    except asyncio.CancelledError:
        log.info("Worker cancelado durante el apagado.")
        raise
    except Exception as exc:
        log.error("Error no capturado en el worker: %s", exc, exc_info=True)


async def _job_sweeper() -> None:
    """Devuelve a PENDING los mensajes atascados en estado PROCESSING."""
    try:
        async with AsyncSessionLocal() as session:
            await recover_orphaned_notifications(session)
    except asyncio.CancelledError:
        log.info("Sweeper cancelado durante el apagado.")
        raise
    except Exception as exc:
        log.error("Error no capturado en el sweeper: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Fábrica del scheduler
# ---------------------------------------------------------------------------
def create_scheduler() -> AsyncIOScheduler:
    """
    Construye y configura el AsyncIOScheduler con los dos jobs periódicos:
      - Worker  : cada 1 segundo   (max_instances=1, coalesce=True)
      - Sweeper : cada 5 minutos   (max_instances=1, coalesce=True)
    """
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _job_worker,
        trigger="interval",
        seconds=1,
        id="worker",
        name="Worker: procesar notificaciones PENDING",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _job_sweeper,
        trigger="interval",
        minutes=5,
        id="sweeper",
        name="Sweeper: recuperar mensajes huérfanos",
        max_instances=1,
        coalesce=True,
    )

    log.info("Scheduler configurado: Worker cada 1s | Sweeper cada 5min.")
    return scheduler
