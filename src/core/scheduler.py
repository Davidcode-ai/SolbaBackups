"""
src/core/scheduler.py — Gestor de Tareas Programadas (APScheduler).

Se encarga de leer los Jobs de la base de datos y programar su ejecución
automática utilizando AsyncIOScheduler.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.db.database import SessionLocal
from src.db import crud

log = logging.getLogger(__name__)

class JobScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        """Inicia el programador en segundo plano."""
        if not self.scheduler.running:
            self.scheduler.start()
            log.info("🚀 Scheduler de APScheduler iniciado.")

    def shutdown(self):
        """Detiene el programador de forma segura."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            log.info("🛑 Scheduler detenido.")

    def load_jobs_from_db(self):
        """
        Carga todos los Jobs activos de la base de datos que tengan
        configurado un cron y los programa en APScheduler.
        """
        # Limpiar trabajos previos para evitar duplicados si se recarga
        self.scheduler.remove_all_jobs()
        
        # Necesitamos una sesión de BD local ya que estamos fuera del contexto de una petición HTTP
        db = SessionLocal()
        try:
            active_jobs = crud.job_get_all(db, is_active=True)
            scheduled_count = 0
            
            for job in active_jobs:
                if job.schedule_type == "cron" and job.schedule_cron:
                    try:
                        trigger = CronTrigger.from_crontab(job.schedule_cron)
                        self.scheduler.add_job(
                            self._execute_scheduled_job,
                            trigger=trigger,
                            args=[job.id, job.name],
                            id=f"job_{job.id}",
                            replace_existing=True
                        )
                        scheduled_count += 1
                    except ValueError as e:
                        log.error(f"Error parseando cron '{job.schedule_cron}' para el Job {job.id}: {e}")
            
            log.info(f"✅ Se han cargado {scheduled_count} jobs programados desde la BD.")
        finally:
            db.close()

    async def _execute_scheduled_job(self, job_id: int, job_name: str):
        """
        Función que ejecuta APScheduler cuando salta el cron.
        (Integración temporal con log de aviso).
        """
        log.info(f"⏰ ¡CRON ACTIVADO! Ejecutando backup programado para el Job ID {job_id} ('{job_name}')...")

# Instancia global del scheduler
scheduler_manager = JobScheduler()
