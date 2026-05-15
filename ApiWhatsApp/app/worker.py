import os
import logging
import httpx
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import WhatsAppNotification, NotificationStatus

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración de la API de Meta (leída del .env vía database.py → load_dotenv)
# ---------------------------------------------------------------------------
_META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
_META_ACCESS_TOKEN    = os.getenv("META_ACCESS_TOKEN", "")
_META_API_VERSION     = os.getenv("META_API_VERSION", "v19.0")
_META_API_URL         = (
    f"https://graph.facebook.com/{_META_API_VERSION}"
    f"/{_META_PHONE_NUMBER_ID}/messages"
)


import json

async def send_message_to_meta(
    client: httpx.AsyncClient,
    phone: str,
    content_text: str,
) -> tuple[bool, str]:
    """
    Envía un mensaje vía la WhatsApp Cloud API de Meta.

    Detecta automáticamente el formato de `content_text`:
    - JSON con clave "template_name" → envía un mensaje de tipo TEMPLATE.
    - Texto plano                    → envía un mensaje de tipo TEXT (legacy).

    Returns:
        (True, "")             → Enviado con éxito.
        (False, "descripción") → Error con detalle para logging/retry.
    """
    if not _META_PHONE_NUMBER_ID or not _META_ACCESS_TOKEN:
        return False, (
            "Credenciales de Meta no configuradas. "
            "Asegúrate de definir META_PHONE_NUMBER_ID y META_ACCESS_TOKEN en el .env."
        )

    headers = {
        "Authorization": f"Bearer {_META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    # ── Detectar tipo de mensaje ──────────────────────────────────────────
    try:
        data = json.loads(content_text)
        is_template = isinstance(data, dict) and "template_name" in data
    except (json.JSONDecodeError, TypeError):
        is_template = False
        data = {}

    if is_template:
        # Mensaje de tipo TEMPLATE (desde la API REST)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "template",
            "template": {
                "name": data["template_name"],
                "language": {"code": data.get("language_code", "en_US")},
            },
        }
        # Si hay variables de componente las añadimos
        vars_ = data.get("template_vars", [])
        if vars_:
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(v)} for v in vars_],
                }
            ]
    else:
        # Mensaje de texto plano (legacy / test_notification.py)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": content_text},
        }

    try:
        response = await client.post(_META_API_URL, json=payload, headers=headers)

        if response.status_code == 200:
            return True, ""

        error_data   = response.json() if response.content else {}
        error_detail = (
            error_data.get("error", {}).get("message")
            or response.text[:300]
        )
        log.warning(
            "Meta API respondió %s para el teléfono %s: %s",
            response.status_code, phone, error_detail,
        )
        return False, f"HTTP {response.status_code}: {error_detail}"

    except httpx.TimeoutException:
        return False, "Timeout al conectar con la API de Meta (>5s)."
    except httpx.RequestError as exc:
        return False, f"Error de red al conectar con Meta: {exc}"


async def process_pending_notifications(db_session: AsyncSession) -> None:
    """
    Worker principal — ciclo de procesamiento:

    1. SELECT ... FOR UPDATE SKIP LOCKED → toma hasta 50 mensajes PENDING.
       SKIP LOCKED garantiza que instancias horizontales no compitan
       por el mismo registro (mitigación de condiciones de carrera).
    2. Marca en bloque como PROCESSING (commit rápido para liberar locks).
    3. Envía cada mensaje a Meta de forma aislada (try/except por mensaje).
    4. Actualiza el estado final:
       - SENT → éxito.
       - retry_count < max_retries → vuelve a PENDING para reintento.
       - retry_count >= max_retries → FAILED definitivo.
    5. Persiste todos los estados en un único commit final.
    """
    stmt = (
        select(WhatsAppNotification)
        .where(WhatsAppNotification.status == NotificationStatus.PENDING)
        .limit(50)
        .with_for_update(skip_locked=True)
    )

    result        = await db_session.execute(stmt)
    notifications = result.scalars().all()

    # Retorno temprano si no hay nada que procesar (sin 'continue' ni 'break')
    if not notifications:
        return

    log.info("Worker: %d notificación(es) PENDING encontrada(s).", len(notifications))

    # ── Fase 1: Marcar como PROCESSING (commit atómico) ───────────────────
    for notif in notifications:
        notif.status       = NotificationStatus.PROCESSING
        notif.processed_at = datetime.now(timezone.utc)

    await db_session.commit()

    # ── Fase 2: Enviar a Meta (error aislado por mensaje) ─────────────────
    sent_count   = 0
    retry_count  = 0
    failed_count = 0

    async with httpx.AsyncClient(timeout=5.0) as client:
        for notif in notifications:
            try:
                success, error_msg = await send_message_to_meta(
                    client,
                    notif.phone_number,
                    notif.content_text,
                )
            except Exception as exc:
                # Captura cualquier excepción inesperada de la función de envío
                success   = False
                error_msg = f"Excepción inesperada en send_message_to_meta: {exc}"
                log.error(error_msg)

            if success:
                notif.status    = NotificationStatus.SENT
                notif.error_log = None
                sent_count += 1

            else:
                notif.retry_count += 1
                notif.error_log    = error_msg

                if notif.retry_count >= notif.max_retries:
                    # Máximo de reintentos alcanzado → FAILED definitivo
                    notif.status = NotificationStatus.FAILED
                    failed_count += 1
                    log.error(
                        "Notificación %s marcada como FAILED definitivo tras %d intentos. "
                        "Destino: %s | Error: %s",
                        notif.id, notif.retry_count, notif.phone_number, error_msg,
                    )
                else:
                    # Aún tiene reintentos disponibles → vuelve a PENDING
                    notif.status       = NotificationStatus.PENDING
                    notif.processed_at = None
                    retry_count += 1
                    log.warning(
                        "Notificación %s volverá a PENDING (intento %d/%d). "
                        "Destino: %s | Error: %s",
                        notif.id, notif.retry_count, notif.max_retries,
                        notif.phone_number, error_msg,
                    )

    # ── Fase 3: Persistir estados finales ─────────────────────────────────
    await db_session.commit()

    log.info(
        "Worker completado: %d enviados | %d a reintentar | %d fallidos definitivos.",
        sent_count, retry_count, failed_count,
    )
