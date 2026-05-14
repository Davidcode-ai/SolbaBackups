import datetime
from src.db import crud
from src.db.models import AppSetting

def test_crud_job_lifecycle(db_session):
    # Crear
    job_data = {
        "name": "CRUD Job",
        "db_type": "mysql",
        "db_name": "db1"
    }
    job = crud.job_create(db_session, job_data)
    assert job.id is not None
    assert job.name == "CRUD Job"
    
    # Leer
    fetched = crud.job_get_by_id(db_session, job.id)
    assert fetched.name == "CRUD Job"
    
    fetched_all = crud.job_get_all(db_session)
    assert len(fetched_all) == 1
    
    # Actualizar
    updated = crud.job_update(db_session, job.id, {"db_name": "db2"})
    assert updated.db_name == "db2"
    
    # Eliminar
    success = crud.job_delete(db_session, job.id)
    assert success is True
    assert crud.job_get_by_id(db_session, job.id) is None

def test_crud_history_and_logs_cascade(db_session):
    job = crud.job_create(db_session, {"name": "Cascade Job", "db_type": "mysql"})
    
    # Crear historial
    run = crud.run_create(db_session, job.id, job.name)
    assert run.status == "running"
    
    # Crear logs para el historial
    log1 = crud.log_add(db_session, run.id, "INFO", "START", "Starting backup")
    log2 = crud.log_add(db_session, run.id, "ERROR", "DUMP", "Failed to dump")
    
    # Comprobar que existen
    logs = crud.log_get_by_run(db_session, run.id)
    assert len(logs) == 2
    
    # Finalizar historial
    run_finished = crud.run_finish(db_session, run.id, "error")
    assert run_finished.status == "error"
    assert run_finished.duration_secs is not None
    
    # Borrar el JOB y comprobar cascada
    crud.job_delete(db_session, job.id)
    
    # El run debería haberse borrado
    assert crud.run_get_by_id(db_session, run.id) is None
    # Los logs deberían haberse borrado
    assert len(crud.log_get_by_run(db_session, run.id)) == 0

def test_crud_history_purge_old(db_session):
    job = crud.job_create(db_session, {"name": "Purge Job", "db_type": "mysql"})
    
    # Crear historial antiguo (hace 10 días)
    old_run = crud.run_create(db_session, job.id, job.name)
    old_run.started_at = datetime.datetime.utcnow() - datetime.timedelta(days=10)
    db_session.commit()
    
    # Crear historial nuevo (hace 1 día)
    new_run = crud.run_create(db_session, job.id, job.name)
    new_run.started_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    db_session.commit()
    
    # Purgar más antiguos a 5 días
    count = crud.history_purge_old(db_session, retention_days=5)
    assert count == 1
    
    # Validar
    assert crud.run_get_by_id(db_session, old_run.id) is None
    assert crud.run_get_by_id(db_session, new_run.id) is not None

def test_crud_settings(db_session):
    # Setting get default
    val = crud.setting_get(db_session, "non_existent", "default_val")
    assert val == "default_val"
    
    # Setting set
    crud.setting_set(db_session, "test_key", {"foo": "bar"})
    val = crud.setting_get(db_session, "test_key")
    assert val == {"foo": "bar"}
    
    # Setting set many
    crud.setting_set_many(db_session, {"key1": 1, "key2": 2})
    all_settings = crud.setting_get_all(db_session)
    assert all_settings["key1"] == 1
    assert all_settings["key2"] == 2
