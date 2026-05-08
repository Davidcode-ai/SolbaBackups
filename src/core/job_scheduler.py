"""
src/core/job_scheduler.py — Programador Automático de Tareas.

Utiliza APScheduler (AsyncIOScheduler) para ejecutar automáticamente
los Jobs de backup en el Event Loop de FastAPI sin bloquear el servidor.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.core.job_manager import JobManager
from src.db import crud
from src.db.database import SessionLocal

log = logging.getLogger(__name__)

class JobScheduler:
    """
    Gestiona el ciclo de vida del programador de backups automáticos.
    """

    def __init__(self, job_manager: JobManager):
        self.job_manager = job_manager
        # Inicializamos el scheduler asíncrono
        self.scheduler = AsyncIOScheduler()

    def start(self):
        """Inicia el programador de tareas."""
        if not self.scheduler.running:
            self.scheduler.start()
            log.info("JobScheduler iniciado correctamente (AsyncIOScheduler).")

    def stop(self):
        """Detiene el programador de forma limpia."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            log.info("JobScheduler detenido.")

    def load_jobs_from_db(self):
        """
        Lee todos los jobs activos de la BD y los programa en el scheduler.
        
        Abre una sesión de base de datos efímera para obtener la lista completa
        de Jobs activos. Para cada Job con un 'schedule_type' válido (distinto
        de 'manual'), lo inserta en el APScheduler. Se llama típicamente
        durante el startup de la aplicación.
        
        Returns:
            None
        """
        # Se necesita una sesión de base de datos efímera para la consulta
        db = SessionLocal()
        try:
            jobs = crud.job_get_all(db, is_active=True)
            count = 0
            for job in jobs:
                if job.schedule_type and job.schedule_type != "manual":
                    if self.add_job(job):
                        count += 1
            log.info(f"Se cargaron {count} jobs automáticos desde la BD.")
        finally:
            db.close()

    def add_job(self, job) -> bool:
        """
        Añade (o actualiza) la programación de un Job en el scheduler.
        
        Convierte la configuración del Job (frecuencia, intervalo o cron) a un
        Trigger compatible con APScheduler. Si el Job ya estaba programado,
        lo reemplaza para aplicar cualquier cambio de configuración.
        
        Args:
            job (JobBase): El objeto del Job extraído de la base de datos que
                           contiene las propiedades 'id', 'schedule_type', etc.
                           
        Returns:
            bool: True si el Job fue parseado y programado con éxito, False
                  si hubo un error en la configuración o el formato cron.
        """
        job_id_str = f"job_{job.id}"
        
        # Eliminar si ya existía para asegurar que reemplazamos la configuración
        self.remove_job(job.id)

        # Normalizar valores del frontend (español) al formato interno
        ALIASES = {
            "diario":   "daily",
            "daily":    "daily",
            "semanal":  "weekly",
            "weekly":   "weekly",
            "mensual":  "monthly",
            "monthly":  "monthly",
            "interval": "interval",
            "cron":     "cron",
        }
        schedule_type = ALIASES.get((job.schedule_type or "").lower())

        trigger = None
        if schedule_type == "daily":
            # Por defecto a las 02:00 AM todos los días
            trigger = CronTrigger(hour=2, minute=0)
        elif schedule_type == "weekly":
            # Por defecto Domingos a las 02:00 AM
            trigger = CronTrigger(day_of_week='sun', hour=2, minute=0)
        elif schedule_type == "monthly":
            # Por defecto el día 1 de cada mes a las 02:00 AM
            trigger = CronTrigger(day=1, hour=2, minute=0)
        elif schedule_type == "interval":
            minutes = job.schedule_interval_minutes or 60
            trigger = IntervalTrigger(minutes=minutes)
        elif schedule_type == "cron":
            if not job.schedule_cron:
                log.error(f"El Job {job.id} es 'cron' pero no tiene 'schedule_cron' definido.")
                return False
            try:
                trigger = CronTrigger.from_crontab(job.schedule_cron)
            except Exception as e:
                log.error(f"Error parseando cron ({job.schedule_cron}) para el Job {job.id}: {e}")
                return False
        else:
            log.warning(f"El schedule_type '{job.schedule_type}' no es programable (se requiere daily/weekly/monthly/interval/cron).")
            return False

        try:
            # Añadir la tarea al scheduler
            # max_instances=1: Seguridad crítica
            job_obj = self.scheduler.add_job(
                self._execute_job,
                trigger=trigger,
                id=job_id_str,
                args=[job.id],
                max_instances=1,
                coalesce=True, # Si el servidor estuvo apagado y se perdieron ejecuciones, corre solo 1 vez
                name=f"Backup {job.name}"
            )
            log.info(f"Job {job.id} programado con éxito. Próxima ejecución: {job_obj.next_run_time}")
            return True
        except Exception as e:
            log.error(f"Error al añadir el Job {job.id} al scheduler: {e}")
            return False

    def remove_job(self, job_id: int):
        """
        Elimina un Job del scheduler de forma segura.
        
        Busca el Job por su ID unívoco (job_{id}). Si existe, lo remueve
        inmediatamente para que no ocurran futuras ejecuciones programadas.
        
        Args:
            job_id (int): El identificador único del Job en la base de datos.
            
        Returns:
            None
        """
        job_id_str = f"job_{job_id}"
        if self.scheduler.get_job(job_id_str):
            self.scheduler.remove_job(job_id_str)
            log.info(f"Job {job_id} desprogramado del scheduler.")

    async def _execute_job(self, job_id: int):
        """
        Desencadena asíncronamente el pipeline de backup.
        
        Esta es la función callback interna que es invocada automáticamente
        por el Event Loop de APScheduler cuando se dispara un trigger de tiempo.
        
        Args:
            job_id (int): El identificador único del Job a ejecutar.
            
        Returns:
            None
        """
        log.info(f"Desencadenando ejecución programada (automática) para el Job {job_id}.")
        await self.job_manager.run_job(job_id, trigger="scheduled")
