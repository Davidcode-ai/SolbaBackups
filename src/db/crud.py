"""
src/db/crud.py — Operaciones CRUD sobre la Base de Datos.

Centraliza todas las consultas y mutaciones de la BD para mantener
los routers de la API libres de lógica de persistencia.

Patrón de uso:
    with SessionLocal() as db:
        job = job_get_by_id(db, job_id=1)
"""

import datetime
import json
import logging
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.db.models import AppSetting, Job, LogEntry, RunHistory

log = logging.getLogger(__name__)

# ===========================================================================
# JOB CRUD
# ===========================================================================

def job_get_all(
    db: Session,
    is_active: bool | None = None,
    db_type: str | None = None,
) -> list[Job]:
    """
    Devuelve todos los Jobs de la BD ordenados alfabéticamente por nombre.

    Args:
        db:        Sesión activa de SQLAlchemy.
        is_active: Si se indica, filtra solo los Jobs activos (True) o inactivos (False).
        db_type:   Si se indica, filtra por tipo de motor ('postgresql', 'sqlite', etc.).

    Returns:
        Lista de objetos ``Job``. Vacía si no hay coincidencias.
    """
    stmt = select(Job)
    if is_active is not None:
        stmt = stmt.where(Job.is_active == is_active)
    if db_type is not None:
        stmt = stmt.where(Job.db_type == db_type)
    stmt = stmt.order_by(Job.name.asc())
    return list(db.scalars(stmt).all())


def job_get_by_id(db: Session, job_id: int) -> Job | None:
    """
    Recupera un Job por su clave primaria (ID).

    Args:
        db:     Sesión activa de SQLAlchemy.
        job_id: Identificador entero del Job.

    Returns:
        Objeto ``Job`` si existe, ``None`` en caso contrario.
    """
    return db.get(Job, job_id)


def job_get_by_name(db: Session, name: str) -> Job | None:
    """
    Recupera un Job por su nombre exacto (case-sensitive).

    Args:
        db:   Sesión activa de SQLAlchemy.
        name: Nombre del Job a buscar.

    Returns:
        Objeto ``Job`` si existe, ``None`` en caso contrario.
    """
    stmt = select(Job).where(Job.name == name)
    return db.scalars(stmt).first()


def job_create(db: Session, data: dict) -> Job:
    """
    Crea un nuevo Job en la base de datos a partir de un diccionario de datos.

    Si el diccionario contiene una clave ``schedule`` anidada (formato Pydantic),
    la descompone en ``schedule_type``, ``schedule_cron`` e
    ``schedule_interval_minutes`` antes de persistir.

    Args:
        db:   Sesión activa de SQLAlchemy.
        data: Diccionario con los campos del Job. Puede contener la clave
              ``schedule`` con subelementos, o los campos planos directamente.

    Returns:
        Objeto ``Job`` recién creado con su ``id`` asignado por la BD.
    """
    # Aplanar el objeto 'schedule' si viene anidado (desde el modelo Pydantic)
    schedule_data = data.pop("schedule", None)
    if schedule_data:
        data["schedule_type"] = schedule_data.get("schedule_type")
        data["schedule_cron"] = schedule_data.get("cron_expression")
        data["schedule_interval_minutes"] = schedule_data.get("interval_minutes")

    db_job = Job(**data)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


def job_update(db: Session, job_id: int, data: dict) -> Job | None:
    """
    Actualiza los campos de un Job existente.

    Solo actualiza los campos presentes en ``data``; los campos ausentes
    no se modifican. Si el diccionario incluye una clave ``schedule`` anidada,
    se descompone igual que en ``job_create``.

    Args:
        db:     Sesión activa de SQLAlchemy.
        job_id: ID del Job a actualizar.
        data:   Diccionario con los campos a modificar.

    Returns:
        Objeto ``Job`` actualizado, o ``None`` si el ID no existe.
    """
    db_job = db.get(Job, job_id)
    if not db_job:
        return None

    # Aplanar el objeto 'schedule' si viene anidado
    schedule_data = data.pop("schedule", None)
    if schedule_data is not None:
        data["schedule_type"] = schedule_data.get("schedule_type")
        data["schedule_cron"] = schedule_data.get("cron_expression")
        data["schedule_interval_minutes"] = schedule_data.get("interval_minutes")

    for key, value in data.items():
        setattr(db_job, key, value)

    db_job.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_job)
    return db_job


def job_delete(db: Session, job_id: int) -> bool:
    """
    Elimina un Job y, por CASCADE, todo su historial de ejecuciones y logs.

    Args:
        db:     Sesión activa de SQLAlchemy.
        job_id: ID del Job a eliminar.

    Returns:
        ``True`` si el Job existía y fue eliminado. ``False`` si no se encontró.
    """
    db_job = db.get(Job, job_id)
    if not db_job:
        return False
    db.delete(db_job)
    db.commit()
    return True


def job_set_active(db: Session, job_id: int, is_active: bool) -> Job | None:
    """
    Activa o desactiva un Job sin modificar ningún otro campo.

    Un Job inactivo no es seleccionado por el Scheduler para su ejecución
    automática, aunque puede ejecutarse manualmente desde la API.

    Args:
        db:        Sesión activa de SQLAlchemy.
        job_id:    ID del Job a modificar.
        is_active: ``True`` para activar, ``False`` para pausar.

    Returns:
        Objeto ``Job`` actualizado, o ``None`` si el ID no existe.
    """
    db_job = db.get(Job, job_id)
    if not db_job:
        return None
    db_job.is_active = is_active
    db_job.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_job)
    return db_job


# ===========================================================================
# RUN HISTORY CRUD
# ===========================================================================

def run_create(db: Session, job_id: int, job_name: str, trigger: str = "manual") -> RunHistory:
    """
    Abre un nuevo registro de ejecución (run) con estado ``running``.

    Debe llamarse al inicio del pipeline de backup para registrar el comienzo
    del proceso. El run queda en estado ``running`` hasta que se llame a
    ``run_finish``.

    Args:
        db:       Sesión activa de SQLAlchemy.
        job_id:   ID del Job que origina la ejecución.
        job_name: Nombre del Job en el momento de la ejecución (snapshot).
        trigger:  Origen del disparo: ``"manual"``, ``"scheduler"``, etc.

    Returns:
        Objeto ``RunHistory`` creado con ``started_at`` marcado a UTC ahora.
    """
    run = RunHistory(
        job_id=job_id,
        job_name=job_name,
        trigger=trigger,
        status="running",
        started_at=datetime.datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def run_finish(
    db: Session,
    run_id: int,
    status: str,
    file_size_bytes: int | None = None,
    backup_file_path: str | None = None,
    destination_url: str | None = None,
    error_message: str | None = None,
) -> RunHistory | None:
    """
    Cierra un run abierto registrando su resultado final.

    Calcula automáticamente la duración en segundos (``duration_secs``)
    como diferencia entre ``started_at`` y el instante actual.

    Args:
        db:                Sesión activa de SQLAlchemy.
        run_id:            ID del run a cerrar.
        status:            Estado final: ``"success"`` o ``"error"``.
        file_size_bytes:   Tamaño del archivo de backup generado, en bytes.
        backup_file_path:  Ruta local o URL de Google Drive del archivo generado.
        destination_url:   URL pública del destino (usado para backups en la nube).
        error_message:     Mensaje de error si ``status == "error"``.

    Returns:
        Objeto ``RunHistory`` actualizado, o ``None`` si el run_id no existe.
    """
    run = db.get(RunHistory, run_id)
    if not run:
        return None

    now = datetime.datetime.utcnow()
    run.finished_at = now
    run.duration_secs = (now - run.started_at).total_seconds()
    run.status = status
    run.file_size_bytes = file_size_bytes
    run.backup_file_path = backup_file_path
    run.destination_url = destination_url
    run.error_message = error_message

    db.commit()
    db.refresh(run)
    return run


def run_get_all(
    db: Session,
    page: int = 1,
    page_size: int = 25,
    status_filter: str | None = None,
) -> list[RunHistory]:
    """
    Devuelve el historial de ejecuciones paginado, ordenado del más reciente al más antiguo.

    Args:
        db:            Sesión activa de SQLAlchemy.
        page:          Número de página (1-based).
        page_size:     Registros por página.
        status_filter: Si se indica, filtra por estado (``"success"``, ``"error"``, ``"running"``).

    Returns:
        Lista de objetos ``RunHistory``.
    """
    stmt = select(RunHistory)
    if status_filter:
        stmt = stmt.where(RunHistory.status == status_filter)
    stmt = stmt.order_by(desc(RunHistory.started_at)).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt).all())


def run_get_by_job(
    db: Session,
    job_id: int,
    page: int = 1,
    page_size: int = 25,
) -> list[RunHistory]:
    """
    Devuelve el historial de ejecuciones de un Job específico, paginado.

    Args:
        db:        Sesión activa de SQLAlchemy.
        job_id:    ID del Job cuyos runs se quieren consultar.
        page:      Número de página (1-based).
        page_size: Registros por página.

    Returns:
        Lista de objetos ``RunHistory`` del Job, del más reciente al más antiguo.
    """
    stmt = select(RunHistory).where(RunHistory.job_id == job_id)
    stmt = stmt.order_by(desc(RunHistory.started_at)).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt).all())


def run_get_by_id(db: Session, run_id: int) -> RunHistory | None:
    """
    Recupera una ejecución específica por su ID.

    Args:
        db:     Sesión activa de SQLAlchemy.
        run_id: ID de la ejecución.

    Returns:
        Objeto ``RunHistory`` si existe, ``None`` en caso contrario.
    """
    return db.get(RunHistory, run_id)


def run_delete(db: Session, run_id: int) -> bool:
    """
    Elimina un run y, por CASCADE, todos sus ``LogEntry`` asociados.

    Args:
        db:     Sesión activa de SQLAlchemy.
        run_id: ID del run a eliminar.

    Returns:
        ``True`` si el run existía y fue eliminado. ``False`` en caso contrario.
    """
    run = db.get(RunHistory, run_id)
    if not run:
        return False
    db.delete(run)
    db.commit()
    return True


def history_purge_old(db: Session, retention_days: int) -> int:
    """
    Elimina las ejecuciones (y sus logs por CASCADE) más antiguas que ``retention_days``.

    Es la función que ejecuta el Garbage Collector global para respetar la
    política de retención configurada en los Ajustes Globales de la aplicación.

    Args:
        db:             Sesión activa de SQLAlchemy.
        retention_days: Días de antigüedad a partir de los cuales se purga.
                        Si es ``<= 0`` no se elimina nada.

    Returns:
        Número de ejecuciones eliminadas.
    """
    if retention_days <= 0:
        return 0
    
    cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)
    
    # Buscar ejecuciones antiguas
    stmt = select(RunHistory).where(RunHistory.started_at < cutoff_date)
    old_runs = list(db.scalars(stmt).all())
    
    count = len(old_runs)
    for run in old_runs:
        db.delete(run)
        
    db.commit()
    return count


# ===========================================================================
# LOG ENTRY CRUD
# ===========================================================================

def log_add(
    db: Session,
    run_id: int,
    level: str,
    stage: str,
    message: str,
    timestamp: datetime.datetime | None = None,
) -> LogEntry:
    """
    Añade una línea de log estructurada asociada a un run en curso.

    Args:
        db:        Sesión activa de SQLAlchemy.
        run_id:    ID del run al que pertenece este log.
        level:     Severidad: ``"INFO"``, ``"WARNING"``, ``"ERROR"``, ``"DEBUG"``.
        stage:     Etapa del pipeline: ``"EXTRACT"``, ``"COMPRESS"``, ``"UPLOAD"``, etc.
        message:   Texto descriptivo del evento.
        timestamp: Marca de tiempo del evento (UTC). Si es ``None``, se usa ``utcnow()``.

    Returns:
        Objeto ``LogEntry`` persistido con su ``id`` asignado.
    """
    if timestamp is None:
        timestamp = datetime.datetime.utcnow()

    log_entry = LogEntry(
        run_id=run_id,
        level=level,
        stage=stage,
        message=message,
        timestamp=timestamp
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def log_get_by_run(
    db: Session,
    run_id: int,
    level: str | None = None,
    stage: str | None = None,
    after_id: int = 0,
) -> list[LogEntry]:
    """
    Devuelve los logs de un run específico, opcionalmente filtrados.

    Soporta paginación incremental mediante ``after_id`` para recuperar
    solo los logs nuevos en un polling de SSE o WebSocket.

    Args:
        db:       Sesión activa de SQLAlchemy.
        run_id:   ID del run cuyos logs se quieren consultar.
        level:    Si se indica, filtra por severidad (``"ERROR"``, ``"INFO"``...).
        stage:    Si se indica, filtra por etapa del pipeline.
        after_id: Solo devuelve logs con ``id > after_id`` (para streaming incremental).

    Returns:
        Lista de ``LogEntry`` ordenados por ``id`` ascendente.
    """
    stmt = select(LogEntry).where(LogEntry.run_id == run_id, LogEntry.id > after_id)
    if level:
        stmt = stmt.where(LogEntry.level == level)
    if stage:
        stmt = stmt.where(LogEntry.stage == stage)
    stmt = stmt.order_by(LogEntry.id.asc())
    return list(db.scalars(stmt).all())


# ===========================================================================
# APP SETTINGS CRUD
# ===========================================================================

def setting_get(db: Session, key: str, default: Any = None) -> Any:
    """
    Recupera el valor de un ajuste de la aplicación deserializado desde JSON.

    Los ajustes se almacenan como cadenas JSON en la BD para soportar
    valores de cualquier tipo (bool, int, str, dict, list).

    Args:
        db:      Sesión activa de SQLAlchemy.
        key:     Clave única del ajuste (ej.: ``"notify_email"``).
        default: Valor devuelto si la clave no existe en la BD.

    Returns:
        El valor deserializado (Python nativo), o ``default`` si no existe.
    """
    setting = db.get(AppSetting, key)
    if setting is None:
        return default
    try:
        return json.loads(setting.value_json)
    except json.JSONDecodeError:
        return setting.value_json


def setting_set(db: Session, key: str, value: Any) -> AppSetting:
    """
    Crea o actualiza un ajuste de la aplicación.

    El valor se serializa a JSON antes de persistirse, por lo que soporta
    cualquier tipo Python serializable (bool, int, str, dict, list).

    Args:
        db:    Sesión activa de SQLAlchemy.
        key:   Clave única del ajuste.
        value: Valor a almacenar (se serializa automáticamente a JSON).

    Returns:
        Objeto ``AppSetting`` creado o actualizado.
    """
    setting = db.get(AppSetting, key)
    serialized = json.dumps(value)

    if setting:
        setting.value_json = serialized
        setting.updated_at = datetime.datetime.utcnow()
    else:
        setting = AppSetting(key=key, value_json=serialized)
        db.add(setting)

    db.commit()
    db.refresh(setting)
    return setting


def setting_get_all(db: Session) -> dict[str, Any]:
    """
    Devuelve todos los ajustes de la aplicación como un diccionario Python.

    Args:
        db: Sesión activa de SQLAlchemy.

    Returns:
        Diccionario ``{clave: valor}`` con todos los ajustes deserializados.
        Vacío si no hay ninguno configurado.
    """
    stmt = select(AppSetting)
    settings = db.scalars(stmt).all()
    result = {}
    for s in settings:
        try:
            result[s.key] = json.loads(s.value_json)
        except json.JSONDecodeError:
            result[s.key] = s.value_json
    return result


def setting_set_many(db: Session, settings: dict[str, Any]) -> None:
    """
    Crea o actualiza múltiples ajustes en una sola transacción.

    Equivalente a llamar a ``setting_set`` para cada par clave-valor,
    pero más eficiente al hacer un solo ``commit`` al final.

    Args:
        db:       Sesión activa de SQLAlchemy.
        settings: Diccionario ``{clave: valor}`` con los ajustes a persistir.

    Returns:
        None. Los cambios se confirman en la BD al finalizar.
    """
    for key, value in settings.items():
        setting = db.get(AppSetting, key)
        serialized = json.dumps(value)
        if setting:
            setting.value_json = serialized
            setting.updated_at = datetime.datetime.utcnow()
        else:
            setting = AppSetting(key=key, value_json=serialized)
            db.add(setting)
    db.commit()
