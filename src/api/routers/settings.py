"""
src/api/routers/settings.py — Router de Configuración Global de la App.

Permite leer y actualizar la configuración global de SolbaBackups:
notificaciones por email, rutas de herramientas externas (pg_dump, mysqldump),
retención de backups y configuración de logging.

Prefijo del router : /api/v1/settings
Tag OpenAPI        : Settings

Endpoints:
    GET  /          → Obtener la configuración actual.
    PUT  /          → Actualizar la configuración global.
    POST /test-email → Enviar un email de prueba con la configuración actual.

Nota sobre persistencia:
    La configuración global se almacena en la BD SQLite en una tabla
    ``app_settings`` con clave-valor serializado como JSON, lo que permite
    añadir nuevas opciones sin migraciones de esquema.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.core.models import AppSettingsRead, AppSettingsUpdate

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/settings",
    tags=["Settings"],
)


@router.get(
    "/",
    response_model=AppSettingsRead,
    summary="Obtener configuración global",
)
def get_settings(db: Session = Depends(get_db)) -> AppSettingsRead:
    """
    Lee la configuración global de la aplicación desde la BD.

    Si no existe ninguna configuración (primera ejecución), devuelve
    los valores por defecto sin persistirlos.

    Args:
        db: Sesión de BD.

    Returns:
        AppSettingsRead: Configuración actual con todos sus campos.
    """
    pass


@router.put(
    "/",
    response_model=AppSettingsRead,
    summary="Actualizar configuración global",
)
def update_settings(
    settings_in: AppSettingsUpdate,
    db: Session = Depends(get_db),
) -> AppSettingsRead:
    """
    Actualiza uno o más campos de la configuración global.

    Operación de tipo PATCH semántico: sólo se actualizan los campos
    explícitamente incluidos en el body (``exclude_unset=True``).

    Args:
        settings_in: Campos a actualizar.
        db:          Sesión de BD.

    Returns:
        AppSettingsRead: Configuración completa tras la actualización.
    """
    pass


@router.post(
    "/test-email",
    status_code=202,
    summary="Enviar email de prueba",
    description=(
        "Envía un email de prueba usando la configuración SMTP actual "
        "para verificar que las notificaciones funcionan correctamente."
    ),
)
def test_email_notification(db: Session = Depends(get_db)) -> dict:
    """
    Dispara un email de prueba para validar la configuración SMTP.

    Lee la configuración actual de la BD y usa el módulo de notificaciones
    (pendiente de implementar) para enviar un email de prueba.

    Args:
        db: Sesión de BD para leer la configuración.

    Returns:
        dict: ``{"status": "sent", "recipient": "email@example.com"}``

    Raises:
        HTTPException 400: Si no hay configuración SMTP guardada.
        HTTPException 502: Si el servidor SMTP rechaza la conexión.
    """
    pass
