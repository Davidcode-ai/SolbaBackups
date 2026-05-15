"""
app/routes/notifications.py  –  Endpoint REST para encolar notificaciones WhatsApp.

POST /api/v1/notifications
    Recibe el payload validado por Pydantic, crea un registro PENDING
    en la tabla outbox y devuelve HTTP 202 Accepted.

El worker de segundo plano (APScheduler) se encarga de enviar el mensaje
a la API de Meta Cloud en el siguiente ciclo de 1 segundo.
"""
import json
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import WhatsAppNotification, NotificationStatus
from app.schemas import NotificationRequest, NotificationResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Notificaciones"])


@router.post(
    "/notifications",
    response_model=NotificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encolar notificación WhatsApp",
    description=(
        "Encola un mensaje de WhatsApp en el outbox de Supabase. "
        "El worker lo enviará a Meta Cloud API en el próximo ciclo (≤1s). "
        "Devuelve **HTTP 202** inmediatamente para no bloquear al cliente."
    ),
)
async def enqueue_notification(
    payload: NotificationRequest,
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """
    Inserta un registro PENDING en la tabla `whatsapp_notifications`.
    El worker asíncrono en segundo plano lo procesará automáticamente.
    """
    notification_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Serializar las variables del template como JSON compacto
    content_text = json.dumps({
        "template_name":  payload.template_name,
        "language_code":  payload.language_code,
        "template_vars":  payload.template_vars,
    }, ensure_ascii=False)

    stmt = insert(WhatsAppNotification).values(
        id=notification_id,
        phone_number=payload.to,
        content_text=content_text,
        source_system="SolbaBackups",
        status=NotificationStatus.PENDING,
        retry_count=0,
        max_retries=3,
        created_at=now,
    )

    await db.execute(stmt)
    await db.commit()

    log.info(
        "Notificación encolada | id=%s | destino=%s | template=%s",
        notification_id, payload.to, payload.template_name,
    )

    return NotificationResponse(
        id=notification_id,
        status=NotificationStatus.PENDING.value,
        message=(
            f"Notificación encolada correctamente para +{payload.to}. "
            "El worker la procesará en el próximo ciclo."
        ),
    )
