"""
src/scheduler/job_scheduler.py — Integración con APScheduler.

Gestiona el ciclo de vida de las tareas programadas de SolbaBackups
usando APScheduler 3.x con el ``BackgroundScheduler`` (hilos de fondo).

Responsabilidades:
    - Inicializar y arrancar el scheduler con los stores y executors configurados.
    - Registrar jobs de backup como tareas con trigger ``cron`` o ``interval``.
    - Sincronizar el scheduler con la BD al arrancar la app (cargar todos los
      jobs activos con schedule configurado).
    - Cancelar, pausar y reanudar tareas cuando cambia la configuración de un job.
    - Gestionar el apagado limpio en el shutdown de FastAPI.

Nomenclatura de IDs de tareas APScheduler:
    Las tareas de APScheduler se identifican con el string ``"job_{job_id}"``,
    donde ``job_id`` es el ID numérico del Job en la BD. Esto permite localizar
    y modificar fácilmente la tarea de cualquier job.

JobStore:
    Se usa el ``MemoryJobStore`` por simplicidad. Los jobs se recargan de la BD
    al arrancar. Si se necesitara persistencia del scheduler entre reinicios,
    se podría usar ``SQLAlchemyJobStore`` con la misma BD SQLite.

Executor:
    ``ThreadPoolExecutor`` con 4 workers (configurable). Cada ejecución de job
    corre en un hilo del pool, no bloqueando el hilo principal del scheduler.
"""

import logging

from apscheduler.executors.pool import ThreadPoolExecutor as APSThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from src.core.job_runner import run_job_in_background

log = logging.getLogger(__name__)

# ID de tarea APScheduler para un job: f"job_{job_id}"
JOB_ID_PREFIX = "job_"


def create_scheduler() -> BackgroundScheduler:
    """
    Crea y configura una instancia de APScheduler BackgroundScheduler.

    Configuración:
        - JobStore: MemoryJobStore (los jobs se recargan de BD al iniciar).
        - Executor: ThreadPoolExecutor con 4 workers.
        - Timezone: UTC para consistencia cross-timezone.
        - ``misfire_grace_time``: 60 segundos (si el sistema estaba apagado
          y el job debería haber corrido, tiene 60s para ejecutarse).
        - ``coalesce``: True (si hubo múltiples misfires, ejecutar solo una vez).

    Returns:
        BackgroundScheduler: Scheduler configurado pero NO iniciado.
                             Llamar a ``scheduler.start()`` explícitamente.
    """
    pass


def load_jobs_from_db(scheduler: BackgroundScheduler, db: Session, job_manager) -> int:
    """
    Carga todos los jobs activos con schedule de la BD y los registra en APScheduler.

    Se llama una única vez durante el startup de la aplicación FastAPI.
    Jobs con ``is_active=False`` o sin schedule se omiten.

    Args:
        scheduler:   Instancia del scheduler (debe estar iniciada).
        db:          Sesión de BD para consultar los jobs.
        job_manager: Instancia del JobManager para pasarla como argumento
                     al callback de cada tarea registrada.

    Returns:
        int: Número de jobs cargados y registrados exitosamente.
    """
    pass


def schedule_job(
    scheduler: BackgroundScheduler,
    job_id: int,
    job_name: str,
    schedule_type: str,
    cron_expression: str | None,
    interval_minutes: int | None,
    job_manager,
) -> bool:
    """
    Registra o actualiza la tarea programada de un job en APScheduler.

    Si ya existe una tarea con el mismo ID (``job_{job_id}``), la reemplaza
    completamente con la nueva configuración (``scheduler.reschedule_job`` o
    remove + add).

    Args:
        scheduler:         Instancia del BackgroundScheduler.
        job_id:            ID del job en la BD.
        job_name:          Nombre del job (para logging).
        schedule_type:     Tipo de trigger: 'cron' | 'interval'.
        cron_expression:   Expresión cron si ``schedule_type == 'cron'``.
        interval_minutes:  Minutos si ``schedule_type == 'interval'``.
        job_manager:       Instancia del JobManager a pasar al callback.

    Returns:
        bool: ``True`` si la tarea se registró correctamente, ``False`` si hubo error.

    Raises:
        ValueError: Si ``schedule_type`` no es válido o faltan parámetros.
    """
    pass


def unschedule_job(scheduler: BackgroundScheduler, job_id: int) -> bool:
    """
    Elimina la tarea programada de un job del scheduler.

    No lanza error si el job no tenía tarea registrada.

    Args:
        scheduler: Instancia del BackgroundScheduler.
        job_id:    ID del job a desregistrar.

    Returns:
        bool: ``True`` si se encontró y eliminó la tarea, ``False`` si no existía.
    """
    pass


def pause_job(scheduler: BackgroundScheduler, job_id: int) -> bool:
    """
    Pausa la tarea programada sin eliminarla del scheduler.

    La tarea se puede reanudar con ``resume_job`` sin necesidad de
    re-registrarla con todos sus parámetros.

    Args:
        scheduler: Instancia del BackgroundScheduler.
        job_id:    ID del job a pausar.

    Returns:
        bool: ``True`` si se pausó, ``False`` si la tarea no existía.
    """
    pass


def resume_job(scheduler: BackgroundScheduler, job_id: int) -> bool:
    """
    Reanuda una tarea pausada previamente con ``pause_job``.

    Args:
        scheduler: Instancia del BackgroundScheduler.
        job_id:    ID del job a reanudar.

    Returns:
        bool: ``True`` si se reanudó, ``False`` si la tarea no existía o no estaba pausada.
    """
    pass


def get_next_run_time(scheduler: BackgroundScheduler, job_id: int) -> str | None:
    """
    Obtiene el timestamp de la próxima ejecución programada de un job.

    Args:
        scheduler: Instancia del BackgroundScheduler.
        job_id:    ID del job.

    Returns:
        str | None: Timestamp ISO 8601 de la próxima ejecución, o ``None``
                    si el job no tiene tarea registrada o está pausado.
    """
    pass


def _make_trigger(
    schedule_type: str,
    cron_expression: str | None,
    interval_minutes: int | None,
):
    """
    Crea el trigger de APScheduler según el tipo de schedule.

    Args:
        schedule_type:    'cron' | 'interval' | 'daily' | 'weekly' | 'monthly'.
        cron_expression:  Expresión cron de 5 campos (min hora dom mes dow).
        interval_minutes: Intervalo en minutos (para tipo 'interval').

    Returns:
        CronTrigger | IntervalTrigger: Trigger listo para registrar en APScheduler.

    Raises:
        ValueError: Si los parámetros son inconsistentes.
    """
    st = (schedule_type or "").lower()

    if st == "interval":
        minutes = interval_minutes or 60
        return IntervalTrigger(minutes=minutes)

    if cron_expression:
        parts = cron_expression.strip().split()
        if len(parts) == 5:
            return CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
        return CronTrigger.from_crontab(cron_expression)

    if st == "daily":
        return CronTrigger(hour=2, minute=0)

    raise ValueError(
        f"No se pudo crear trigger para schedule_type={schedule_type!r}"
    )


class JobScheduler:
    """
    Fachada sobre APScheduler para registrar jobs de backup desde modelos Job.
    """

    def __init__(self, job_manager=None, scheduler: BackgroundScheduler | None = None) -> None:
        self.job_manager = job_manager
        self.scheduler = scheduler

    def _job_scheduler_id(self, job_id: int) -> str:
        return f"{JOB_ID_PREFIX}{job_id}"

    def add_job(self, job) -> bool:
        """Registra un Job en APScheduler. Devuelve False si es manual o inválido."""
        schedule_type = (getattr(job, "schedule_type", None) or "").lower()
        if schedule_type in ("manual", "none", ""):
            return False

        if self.scheduler is None:
            log.warning("JobScheduler sin instancia APScheduler; omitiendo job %s", job.id)
            return False

        try:
            trigger = _make_trigger(
                schedule_type,
                getattr(job, "schedule_cron", None),
                getattr(job, "schedule_interval_minutes", None),
            )
        except ValueError as exc:
            log.warning("No se programó job %s: %s", job.id, exc)
            return False

        job_id = getattr(job, "id", None)
        if job_id is None:
            return False

        def _callback(jid: int = job_id, jm=self.job_manager) -> None:
            if jm is not None:
                run_job_in_background(jid, jm, trigger="scheduled")

        self.scheduler.add_job(
            _callback,
            trigger=trigger,
            id=self._job_scheduler_id(job_id),
            replace_existing=True,
        )
        return True

    def remove_job(self, job_id: int) -> None:
        """Elimina la tarea programada de un job (silencioso si no existe)."""
        if self.scheduler is None:
            return
        try:
            self.scheduler.remove_job(self._job_scheduler_id(job_id))
        except Exception:
            pass
