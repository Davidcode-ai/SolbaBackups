"""
src/core/models.py — Modelos de Validación de Datos (Pydantic).

Estos modelos actúan como puente entre la API (peticiones/respuestas REST)
y la base de datos (SQLAlchemy). Validan tipos de datos, imponen
restricciones y documentan el esquema de la API automáticamente en Swagger.

Se usa Pydantic v2 (``ConfigDict(from_attributes=True)`` permite
que Pydantic lea datos directamente de objetos SQLAlchemy).
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ===========================================================================
# SCHEDULE CONFIG
# ===========================================================================

class ScheduleConfig(BaseModel):
    """
    Submodelo para la configuración de programación del Job.
    Mapea a los campos ``schedule_*`` en la base de datos.
    """
    schedule_type: str = Field("manual", description="'cron', 'interval' o 'manual'")
    cron_expression: str | None = Field(None, description="Expresión cron, ej. '0 2 * * *'")
    interval_minutes: int | None = Field(None, description="Minutos entre ejecuciones")

    @model_validator(mode='before')
    @classmethod
    def empty_strings_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: (None if v == "" else v) for k, v in data.items()}
        return data

    @field_validator("schedule_type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v and v not in ("cron", "interval", "manual"):
            raise ValueError("schedule_type debe ser 'cron', 'interval' o 'manual'")
        return v


# ===========================================================================
# JOB MODELS
# ===========================================================================

class JobBase(BaseModel):
    """Atributos comunes para lectura, creación y actualización de un Job."""
    name: str = Field(..., max_length=255)
    description: str | None = None
    
    # Base de Datos
    db_type: str | None = Field("postgresql", description="'postgresql', 'mysql', 'sqlserver', 'sqlite'")
    db_host: str | None = None
    db_port: int | None = None
    db_name: str | None = None
    db_user: str | None = None
    db_extra_params: str | None = None
    
    # Procesadores
    compress: bool | None = True
    compress_format: str | None = "zip"
    encrypt: bool | None = False
    
    # Destino
    dest_type: str | None = Field("local", description="'local', 'google_drive'")
    dest_local_path: str | None = None
    dest_retention_days: int | None = Field(None, description="Días de retención")
    dest_gdrive_folder_id: str | None = None
    
    # Programación (Schedule) plana
    schedule_type: Optional[str] = None
    schedule_interval_minutes: Optional[int] = None
    schedule_cron: Optional[str] = None
    
    @model_validator(mode='before')
    @classmethod
    def empty_strings_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            new_data = {k: (None if v == "" else v) for k, v in data.items()}
            # Si el frontend envía 'schedule' como string, lo mapeamos al campo plano 'schedule_type'
            if 'schedule' in new_data:
                sched_val = new_data.pop('schedule')
                if isinstance(sched_val, str):
                    new_data['schedule_type'] = sched_val.lower()
            return new_data
        return data


    @field_validator("db_type")
    @classmethod
    def validate_db_type(cls, v: str | None) -> str | None:
        if v is None:
            return "postgresql"
        allowed = ("postgresql", "mysql", "sqlserver", "sqlite")
        if v not in allowed:
            raise ValueError(f"db_type debe ser uno de: {allowed}")
        return v


class JobCreate(JobBase):
    """Payload para crear un nuevo Job."""
    # Las contraseñas se envían en texto claro en la request POST,
    # y el router/backend las encriptará antes de guardarlas en BD.
    db_password: str | None = None
    encrypt_password: str | None = None


class JobUpdate(BaseModel):
    """
    Payload para actualizar un Job (PATCH/PUT parcial).
    Todos los campos son opcionales.
    """
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    
    db_type: str | None = None
    db_host: str | None = None
    db_port: int | None = None
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None
    db_extra_params: str | None = None
    
    compress: bool | None = None
    compress_format: str | None = None
    encrypt: bool | None = None
    encrypt_password: str | None = None
    
    dest_type: str | None = None
    dest_local_path: str | None = None
    dest_retention_days: int | str | None = None
    dest_gdrive_folder_id: str | None = None
    
    schedule_type: Optional[str] = None
    schedule_interval_minutes: Optional[int] = None
    schedule_cron: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def empty_strings_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            new_data = {k: (None if v == "" else v) for k, v in data.items()}
            # Si el frontend envía 'schedule' como string, lo mapeamos al campo plano 'schedule_type'
            if 'schedule' in new_data:
                sched_val = new_data.pop('schedule')
                if isinstance(sched_val, str):
                    new_data['schedule_type'] = sched_val.lower()
            return new_data
        return data


class JobRead(JobBase):
    """
    Representación del Job que se devuelve al frontend.
    Nunca incluye las contraseñas ni siquiera encriptadas por seguridad.
    """
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Schedule aplanado en BD -> anidado en Pydantic al devolver (si lo requiere)
    # Por simplicidad para el frontend, lo devolvemos plano aquí
    schedule_type: str | None = None
    schedule_cron: str | None = None
    schedule_interval_minutes: int | None = None
    schedule_next_run: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# RUN HISTORY MODELS
# ===========================================================================

class RunHistoryRead(BaseModel):
    """Registro de una ejecución (devuelto al frontend)."""
    id: int
    job_id: int
    job_name: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_secs: float | None = None
    status: str
    trigger: str
    file_size_bytes: int | None = None
    backup_file_path: str | None = None
    destination_url: str | None = None
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# LOG ENTRY MODELS
# ===========================================================================

class LogEntryRead(BaseModel):
    """Una línea de log de una ejecución."""
    id: int
    run_id: int
    timestamp: datetime
    level: str
    stage: str
    message: str

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# APP SETTINGS MODELS
# ===========================================================================

class AppSettingsRead(BaseModel):
    """Lectura de todas las configuraciones globales."""
    settings: dict[str, Any]
    
    model_config = ConfigDict(from_attributes=True)

class AppSettingsUpdate(BaseModel):
    """Payload para actualizar múltiples configuraciones globales."""
    settings: dict[str, Any] | None = None
    
    # El Frontend puede estar enviando los datos planos en lugar de dentro de 'settings'
    # Hacemos que acepte cualquier campo extra.
    model_config = ConfigDict(extra="allow")

    @model_validator(mode='before')
    @classmethod
    def empty_strings_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: (None if v == "" else v) for k, v in data.items()}
        return data
