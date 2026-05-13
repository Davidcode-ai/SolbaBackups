"""
src/core/job_runner.py — Executor de Jobs en Background.

Proporciona la función ``run_job_in_background`` que ejecuta el pipeline
de backup en un hilo de fondo separado del hilo del request HTTP de FastAPI.

Motivación:
    Los backups pueden tardar desde segundos hasta varios minutos.
    Si se ejecutaran de forma síncrona en el hilo del request, FastAPI
    bloquearía la respuesta hasta completar, lo cual es inaceptable para
    una API REST. En su lugar, el endpoint devuelve ``202 Accepted``
    inmediatamente y el backup corre en un ThreadPoolExecutor.

Uso por APScheduler:
    El scheduler también usa este módulo para disparar jobs programados.
    Cada job programado se registra con ``run_job_scheduled`` como función
    callback, que crea su propio contexto de ejecución.

Control de concurrencia:
    Se mantiene un set de ``job_ids`` actualmente en ejecución para prevenir
    que el mismo job se ejecute dos veces simultáneamente (por ejemplo,
    si se dispara manualmente mientras ya hay una ejecución programada).

Thread Safety:
    El set de jobs activos usa un ``threading.Lock`` para operaciones atómicas.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from src.core.job_manager import JobManager

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado global del runner (singleton por proceso)
# ---------------------------------------------------------------------------
_executor: ThreadPoolExecutor = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="solba-job",
)
_active_job_ids: set[int] = set()
_lock: threading.Lock = threading.Lock()


def run_job_in_background(
    job_id: int,
    job_manager: JobManager,
    trigger: str = "manual",
) -> bool | None:
    """
    Envía la ejecución de un job al ThreadPoolExecutor.

    Primero verifica que el job no esté ya en ejecución. Si está libre,
    lo marca como activo y lo envía al pool de hilos.

    Args:
        job_id:      ID del job a ejecutar.
        job_manager: Instancia del JobManager que ejecutará el pipeline.
        trigger:     Origen de la ejecución: 'manual' | 'scheduled'.

    Returns:
        True  → job enviado al pool correctamente.
        None  → el job ya estaba en ejecución (conflicto ignorado).
    """
    with _lock:
        if job_id in _active_job_ids:
            log.warning(
                "Job %s ya está en ejecución. Solicitud ignorada (trigger=%s).",
                job_id, trigger,
            )
            return None
        _active_job_ids.add(job_id)

    _executor.submit(_run_and_release, job_id, job_manager, trigger)
    log.info("Job %s enviado al pool de hilos (trigger=%s).", job_id, trigger)
    return True


def _run_and_release(job_id: int, job_manager: JobManager, trigger: str) -> None:
    """
    Ejecuta el job y libera su slot en ``_active_job_ids`` al terminar.

    Esta es la función real que corre dentro del hilo del ThreadPoolExecutor.
    Garantiza que el job_id se elimine de ``_active_job_ids`` en el ``finally``,
    incluso si la ejecución lanza una excepción no capturada.

    Args:
        job_id:      ID del job.
        job_manager: Instancia del JobManager.
        trigger:     Origen de la ejecución.
    """
    from src.db.database import SessionLocal
    from src.db import crud
    from src.core.notifications import send_email_notification
    from src.notifications.whatsapp import whatsapp_notifier

    db = SessionLocal()
    success = False
    job_name = "Desconocido"
    try:
        job = crud.job_get_by_id(db, job_id)
        if job:
            job_name = job.name

        # Ejecutar el pipeline de backup bloqueante real
        import asyncio
        asyncio.run(job_manager.run_job(job_id, trigger=trigger))
        success = True
    except Exception as e:
        log.error(f"Error crítico no controlado en hilo background para Job {job_id}: {e}")
    finally:
        with _lock:
            _active_job_ids.discard(job_id)
            log.debug(f"Job {job_id} liberado de _active_job_ids.")


def is_job_running(job_id: int) -> bool:
    """
    Comprueba si un job está actualmente en ejecución.

    Args:
        job_id: ID del job a comprobar.

    Returns:
        bool: ``True`` si el job está en ejecución, ``False`` en caso contrario.
    """
    with _lock:
        return job_id in _active_job_ids


def get_active_jobs() -> set[int]:
    """
    Devuelve una copia del set de IDs de jobs actualmente en ejecución.

    Returns:
        set[int]: IDs de jobs en ejecución (copia thread-safe).
    """
    with _lock:
        return set(_active_job_ids)


def shutdown_executor(wait: bool = True) -> None:
    """
    Apaga el ThreadPoolExecutor de forma ordenada.

    Se llama desde el lifespan de FastAPI durante el shutdown de la aplicación.

    Args:
        wait: Si ``True`` (defecto), espera a que terminen los jobs en curso
              antes de apagar. Si ``False``, fuerza el apagado inmediato.
    """
    log.info("Apagando ThreadPoolExecutor (wait=%s)...", wait)
    _executor.shutdown(wait=wait)
    log.info("ThreadPoolExecutor apagado correctamente.")
