"""
Planificador de copias de seguridad.

Soporta frecuencias:
  - daily   : una vez al día a la hora especificada
  - weekly  : una vez a la semana (día + hora)
  - monthly : una vez al mes (día del mes + hora)
  - weekdays: días concretos de la semana (lista + hora)
  - interval: cada N minutos/horas (para pruebas / desarrollo)

Internamente usa la librería `schedule` para gestionar las tareas.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import schedule

logger = logging.getLogger(__name__)

# Mapeo de nombres de días en español/inglés a los métodos de `schedule`
_DAY_MAP = {
    "monday": schedule.every().monday,
    "lunes": schedule.every().monday,
    "tuesday": schedule.every().tuesday,
    "martes": schedule.every().tuesday,
    "wednesday": schedule.every().wednesday,
    "miercoles": schedule.every().wednesday,
    "miércoles": schedule.every().wednesday,
    "thursday": schedule.every().thursday,
    "jueves": schedule.every().thursday,
    "friday": schedule.every().friday,
    "viernes": schedule.every().friday,
    "saturday": schedule.every().saturday,
    "sabado": schedule.every().saturday,
    "sábado": schedule.every().saturday,
    "sunday": schedule.every().sunday,
    "domingo": schedule.every().sunday,
}


class ScheduledJob:
    """Representa una tarea de backup programada."""

    def __init__(
        self,
        name: str,
        frequency: str,
        at_time: str,
        job_fn: Callable,
        job_kwargs: Optional[Dict[str, Any]] = None,
        days: Optional[List[str]] = None,
        day_of_month: int = 1,
        interval_minutes: int = 60,
    ) -> None:
        """
        Args:
            name:             Nombre identificador de la tarea.
            frequency:        'daily' | 'weekly' | 'monthly' | 'weekdays' | 'interval'
            at_time:          Hora en formato 'HH:MM' (ignorado para 'interval').
            job_fn:           Función a llamar cuando se dispara la tarea.
            job_kwargs:       Argumentos para job_fn.
            days:             Lista de días para frecuencia 'weekdays' o
                              día único para 'weekly' (p.ej. ['monday']).
            day_of_month:     Día del mes para frecuencia 'monthly' (1-28).
            interval_minutes: Intervalo en minutos para frecuencia 'interval'.
        """
        self.name = name
        self.frequency = frequency
        self.at_time = at_time
        self.job_fn = job_fn
        self.job_kwargs: Dict[str, Any] = job_kwargs or {}
        self.days: List[str] = days or []
        self.day_of_month = day_of_month
        self.interval_minutes = interval_minutes
        self._schedule_jobs: List[schedule.Job] = []

    # ------------------------------------------------------------------
    # Registro en el scheduler
    # ------------------------------------------------------------------
    def register(self) -> None:
        """Registra la tarea en el scheduler global de `schedule`."""
        freq = self.frequency.lower()

        if freq == "daily":
            job = schedule.every().day.at(self.at_time).do(self._run_wrapped)
            self._schedule_jobs.append(job)

        elif freq == "weekly":
            day_name = (self.days[0] if self.days else "monday").lower()
            day_scheduler = _DAY_MAP.get(day_name)
            if day_scheduler is None:
                raise ValueError(f"Día no reconocido: {day_name!r}")
            job = day_scheduler.at(self.at_time).do(self._run_wrapped)
            self._schedule_jobs.append(job)

        elif freq == "monthly":
            # `schedule` no soporta 'mensual' nativamente; usamos daily
            # y filtramos el día del mes en el wrapper.
            job = schedule.every().day.at(self.at_time).do(self._run_monthly_wrapped)
            self._schedule_jobs.append(job)

        elif freq == "weekdays":
            for day_name in self.days:
                day_scheduler = _DAY_MAP.get(day_name.lower())
                if day_scheduler is None:
                    logger.warning("Día no reconocido, ignorado: %s", day_name)
                    continue
                job = day_scheduler.at(self.at_time).do(self._run_wrapped)
                self._schedule_jobs.append(job)

        elif freq == "interval":
            job = schedule.every(self.interval_minutes).minutes.do(self._run_wrapped)
            self._schedule_jobs.append(job)

        else:
            raise ValueError(f"Frecuencia no soportada: {self.frequency!r}")

        logger.info(
            "Tarea '%s' registrada con frecuencia '%s'.", self.name, self.frequency
        )

    def cancel(self) -> None:
        """Cancela todos los jobs registrados por esta tarea."""
        for j in self._schedule_jobs:
            schedule.cancel_job(j)
        self._schedule_jobs.clear()
        logger.info("Tarea '%s' cancelada.", self.name)

    # ------------------------------------------------------------------
    # Wrappers de ejecución
    # ------------------------------------------------------------------
    def _run_wrapped(self) -> None:
        logger.info("Ejecutando tarea: %s", self.name)
        try:
            self.job_fn(**self.job_kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error en tarea '%s': %s", self.name, exc)

    def _run_monthly_wrapped(self) -> None:
        if datetime.now().day == self.day_of_month:
            self._run_wrapped()


# ---------------------------------------------------------------------------
# Gestor del planificador
# ---------------------------------------------------------------------------
class BackupScheduler:
    """Gestiona el ciclo de vida de las tareas programadas."""

    def __init__(self) -> None:
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add_job(self, job: ScheduledJob) -> None:
        """Añade y registra una nueva tarea."""
        if job.name in self._jobs:
            logger.warning("La tarea '%s' ya existe. Cancelando la anterior.", job.name)
            self._jobs[job.name].cancel()
        job.register()
        self._jobs[job.name] = job

    def remove_job(self, name: str) -> bool:
        """Elimina una tarea por nombre. Devuelve True si existía."""
        job = self._jobs.pop(name, None)
        if job:
            job.cancel()
            return True
        return False

    def list_jobs(self) -> List[Dict[str, Any]]:
        """Devuelve información sobre las tareas registradas."""
        return [
            {
                "name": j.name,
                "frequency": j.frequency,
                "at_time": j.at_time,
                "days": j.days,
            }
            for j in self._jobs.values()
        ]

    # ------------------------------------------------------------------
    # Ciclo de ejecución
    # ------------------------------------------------------------------
    def start(self, blocking: bool = True, tick_seconds: float = 1.0) -> None:
        """
        Inicia el loop del planificador.

        Args:
            blocking:     Si True, bloquea el hilo actual.
                          Si False, lo lanza en un hilo separado (daemon).
            tick_seconds: Intervalo de comprobación en segundos.
        """
        self._running = True
        if blocking:
            self._loop(tick_seconds)
        else:
            self._thread = threading.Thread(
                target=self._loop,
                args=(tick_seconds,),
                daemon=True,
                name="BackupScheduler",
            )
            self._thread.start()
            logger.info("Planificador iniciado en hilo daemon.")

    def stop(self) -> None:
        """Detiene el planificador."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Planificador detenido.")

    def _loop(self, tick: float) -> None:
        while self._running:
            schedule.run_pending()
            time.sleep(tick)
