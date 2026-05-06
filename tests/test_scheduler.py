"""
Tests del planificador de tareas.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
import schedule

from src.scheduler.scheduler import BackupScheduler, ScheduledJob


@pytest.fixture(autouse=True)
def clear_schedule():
    """Limpia el scheduler global de `schedule` antes de cada test."""
    schedule.clear()
    yield
    schedule.clear()


class TestScheduledJob:
    def test_daily_registration(self):
        fn = MagicMock()
        job = ScheduledJob("test_daily", "daily", "03:00", fn)
        job.register()
        assert len(job._schedule_jobs) == 1
        job.cancel()

    def test_weekly_registration(self):
        fn = MagicMock()
        job = ScheduledJob("test_weekly", "weekly", "08:00", fn, days=["monday"])
        job.register()
        assert len(job._schedule_jobs) == 1
        job.cancel()

    def test_weekdays_registration(self):
        fn = MagicMock()
        job = ScheduledJob(
            "test_weekdays",
            "weekdays",
            "09:00",
            fn,
            days=["lunes", "miercoles", "viernes"],
        )
        job.register()
        assert len(job._schedule_jobs) == 3
        job.cancel()

    def test_monthly_registration(self):
        fn = MagicMock()
        job = ScheduledJob("test_monthly", "monthly", "00:00", fn, day_of_month=1)
        job.register()
        assert len(job._schedule_jobs) == 1
        job.cancel()

    def test_interval_registration(self):
        fn = MagicMock()
        job = ScheduledJob("test_interval", "interval", "", fn, interval_minutes=30)
        job.register()
        assert len(job._schedule_jobs) == 1
        job.cancel()

    def test_unknown_frequency_raises(self):
        fn = MagicMock()
        job = ScheduledJob("test_bad", "biweekly", "12:00", fn)
        with pytest.raises(ValueError, match="Frecuencia no soportada"):
            job.register()

    def test_unknown_day_raises(self):
        fn = MagicMock()
        job = ScheduledJob("test_bad_day", "weekly", "12:00", fn, days=["martes_malo"])
        with pytest.raises(ValueError, match="Día no reconocido"):
            job.register()

    def test_cancel_clears_jobs(self):
        fn = MagicMock()
        job = ScheduledJob("test_cancel", "daily", "06:00", fn)
        job.register()
        assert len(schedule.jobs) > 0
        job.cancel()
        assert len(job._schedule_jobs) == 0

    def test_run_wrapped_calls_fn(self):
        fn = MagicMock()
        job = ScheduledJob("test_run", "daily", "00:00", fn, job_kwargs={"x": 1})
        job._run_wrapped()
        fn.assert_called_once_with(x=1)

    def test_run_wrapped_catches_exceptions(self):
        fn = MagicMock(side_effect=RuntimeError("boom"))
        job = ScheduledJob("test_exc", "daily", "00:00", fn)
        # No debe lanzar excepción
        job._run_wrapped()

    def test_monthly_only_runs_on_correct_day(self):
        from datetime import datetime

        fn = MagicMock()
        job = ScheduledJob("test_monthly_day", "monthly", "00:00", fn, day_of_month=1)

        with patch("src.scheduler.scheduler.datetime") as mock_dt:
            # Día 1 → debe ejecutarse
            mock_dt.now.return_value = datetime(2025, 1, 1, 0, 0, 0)
            job._run_monthly_wrapped()
            fn.assert_called_once()

            fn.reset_mock()

            # Día 15 → no debe ejecutarse
            mock_dt.now.return_value = datetime(2025, 1, 15, 0, 0, 0)
            job._run_monthly_wrapped()
            fn.assert_not_called()


class TestBackupScheduler:
    def test_add_and_list_jobs(self):
        scheduler = BackupScheduler()
        fn = MagicMock()
        job = ScheduledJob("job1", "daily", "12:00", fn)
        scheduler.add_job(job)

        jobs = scheduler.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["name"] == "job1"
        scheduler.remove_job("job1")

    def test_remove_existing_job(self):
        scheduler = BackupScheduler()
        fn = MagicMock()
        job = ScheduledJob("job2", "daily", "12:00", fn)
        scheduler.add_job(job)
        removed = scheduler.remove_job("job2")
        assert removed is True
        assert len(scheduler.list_jobs()) == 0

    def test_remove_nonexistent_job(self):
        scheduler = BackupScheduler()
        removed = scheduler.remove_job("does_not_exist")
        assert removed is False

    def test_add_duplicate_replaces(self):
        scheduler = BackupScheduler()
        fn = MagicMock()
        job1 = ScheduledJob("dup", "daily", "10:00", fn)
        job2 = ScheduledJob("dup", "daily", "11:00", fn)
        scheduler.add_job(job1)
        scheduler.add_job(job2)

        jobs = scheduler.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["at_time"] == "11:00"
        scheduler.remove_job("dup")

    def test_start_stop_nonblocking(self):
        scheduler = BackupScheduler()
        scheduler.start(blocking=False, tick_seconds=0.05)
        time.sleep(0.1)
        scheduler.stop()
        assert not scheduler._running
