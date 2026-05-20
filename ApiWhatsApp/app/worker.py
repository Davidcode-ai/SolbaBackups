"""
app/worker.py — Outbox Worker con Patrón Estrategia para proveedores de WhatsApp.

Proveedores disponibles (WHATSAPP_PROVIDER en .env):
    META  → Meta WhatsApp Cloud API (oficial, requiere Business Account).
    WAHA  → WhatsApp HTTP API (WAHA, Docker, basado en whatsapp-web.js).

El worker leerá la variable de entorno en cada ciclo para respetar cambios
en caliente sin reiniciar el proceso.
"""
import os
import json
import logging
import httpx
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import WhatsAppNotification, NotificationStatus

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración de Meta Cloud API (leída al importar el módulo)
# load_dotenv(override=True) ya fue invocado en database.py antes de esto.
# ---------------------------------------------------------------------------
_META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
_META_ACCESS_TOKEN    = os.getenv("META_ACCESS_TOKEN", "")
_META_API_VERSION     = os.getenv("META_API_VERSION", "v19.0")
_META_API_URL         = (
    f"https://graph.facebook.com/{_META_API_VERSION}"
    f"/{_META_PHONE_NUMBER_ID}/messages"
)


# ===========================================================================
# ESTRATEGIA A: Meta WhatsApp Cloud API (proveedor oficial)
# ===========================================================================

async def _send_via_meta(
    client: httpx.AsyncClient,
    phone: str,
    content_text: str,
) -> tuple[bool, str]:
    """
    Envía un mensaje vía la WhatsApp Cloud API de Meta.

    Detecta automáticamente el formato de `content_text`:
    - JSON con clave "template_name" → mensaje de tipo TEMPLATE.
    - Texto plano                    → mensaje de tipo TEXT (legacy).

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


# Alias público para compatibilidad con cualquier código externo que lo importe
send_message_to_meta = _send_via_meta


# ===========================================================================
# ESTRATEGIA B: WAHA — WhatsApp HTTP API (Docker / whatsapp-web.js)
# ===========================================================================

async def _send_via_waha(
    client: httpx.AsyncClient,
    phone: str,
    content_text: str,
) -> tuple[bool, str]:
    """
    Envía un mensaje de texto vía WAHA (WhatsApp HTTP API).

    WAHA expone un servidor HTTP local que automatiza WhatsApp Web mediante
    whatsapp-web.js. No requiere Meta Business Account ni aprobación de
    plantillas: funciona con cualquier número de WhatsApp Personal/Business.

    Endpoint: POST {WHATSAPP_WEB_API_URL}/sendText
    Payload:
        {
            "chatId": "<phone>@c.us",
            "text":   "<message_text>"
        }

    La función extrae el texto del mensaje de la siguiente forma:
    - Si content_text es JSON con clave "template_vars": concatena las variables
      en una línea por parámetro, precedidas del nombre del template.
    - Si es texto plano: lo usa directamente.

    Returns:
        (True, "")             → Enviado con éxito (HTTP 200/201).
        (False, "descripción") → Error con detalle para logging/retry.
    """
    waha_base_url = os.getenv("WHATSAPP_WEB_API_URL", "http://waha:3000/api").rstrip("/")
    endpoint      = f"{waha_base_url}/sendText"

    # ── Construir el texto legible para WhatsApp Web ──────────────────────
    try:
        data = json.loads(content_text)
        if isinstance(data, dict) and "template_name" in data:
            # Representación textual del template para envío por WhatsApp Web
            vars_  = data.get("template_vars", [])
            header = f"[{data['template_name']}]"
            body   = "\n".join(str(v) for v in vars_) if vars_ else "(sin parámetros)"
            text   = f"{header}\n{body}"
        else:
            text = content_text
    except (json.JSONDecodeError, TypeError):
        text = content_text

    payload = {
        "chatId": f"{phone}@c.us",
        "text":   text,
    }

    try:
        response = await client.post(endpoint, json=payload)

        if response.status_code in (200, 201):
            return True, ""

        error_detail = response.text[:300]
        log.warning(
            "WAHA API respondió %s para el teléfono %s: %s",
            response.status_code, phone, error_detail,
        )
        return False, f"HTTP {response.status_code}: {error_detail}"

    except httpx.TimeoutException:
        return False, "Timeout al conectar con WAHA (>5s). ¿Está el contenedor corriendo?"
    except httpx.RequestError as exc:
        return False, f"Error de red al conectar con WAHA: {exc}"


# ===========================================================================
# DISPATCHER — selecciona la estrategia según WHATSAPP_PROVIDER
# ===========================================================================

async def _dispatch_send(
    client: httpx.AsyncClient,
    phone: str,
    content_text: str,
) -> tuple[bool, str]:
    """
    Selecciona y ejecuta la estrategia de envío según la variable de entorno
    WHATSAPP_PROVIDER (leída en cada llamada para soportar hot-reload).

    Valores válidos (case-insensitive):
        META  → _send_via_meta
        WAHA  → _send_via_waha

    Cualquier otro valor provoca un fallo inmediato (FAILED) con log descriptivo.
    """
    provider = os.getenv("WHATSAPP_PROVIDER", "META").upper().strip()

    if provider == "META":
        return await _send_via_meta(client, phone, content_text)

    if provider == "WAHA":
        return await _send_via_waha(client, phone, content_text)

    # Proveedor desconocido → fallo inmediato sin reintentar
    error_msg = (
        f"Proveedor desconocido: WHATSAPP_PROVIDER='{provider}'. "
        "Valores válidos: 'META' | 'WAHA'. "
        "Corrígelo en el .env y reinicia el servicio."
    )
    log.error(error_msg)
    return False, error_msg


# ===========================================================================
# WORKER PRINCIPAL — procesar notificaciones PENDING
# ===========================================================================

async def process_pending_notifications(db_session: AsyncSession) -> None:
    """
    Worker principal — ciclo de procesamiento (Outbox Pattern):

    1. SELECT ... FOR UPDATE SKIP LOCKED → toma hasta 50 mensajes PENDING.
       SKIP LOCKED garantiza que instancias horizontales no compitan
       por el mismo registro (mitigación de condiciones de carrera).
    2. Marca en bloque como PROCESSING (commit rápido para liberar locks).
    3. Envía cada mensaje usando la estrategia activa (_dispatch_send).
    4. Actualiza el estado final:
       - SENT     → éxito.
       - PENDING  → retry_count < max_retries, reintentará en el próximo ciclo.
       - FAILED   → retry_count >= max_retries, fallo definitivo.
    5. Persiste todos los estados en un único commit final.

    Restricciones de sintaxis:
        - Sin 'continue', 'pass', 'break' ni 'while True'.
        - Flujo controlado exclusivamente con if/else y retornos tempranos.
    """
    stmt = (
        select(WhatsAppNotification)
        .where(WhatsAppNotification.status == NotificationStatus.PENDING)
        .limit(50)
        .with_for_update(skip_locked=True)
    )

    result        = await db_session.execute(stmt)
    notifications = result.scalars().all()

    # Retorno temprano si no hay nada que procesar
    if not notifications:
        return

    log.info("Worker: %d notificación(es) PENDING encontrada(s).", len(notifications))

    # ── Fase 1: Marcar como PROCESSING (commit atómico) ───────────────────
    for notif in notifications:
        notif.status       = NotificationStatus.PROCESSING
        notif.processed_at = datetime.now(timezone.utc)

    await db_session.commit()

    # ── Fase 2: Enviar usando la estrategia activa ────────────────────────
    sent_count   = 0
    retry_count  = 0
    failed_count = 0

    async with httpx.AsyncClient(timeout=5.0) as client:
        for notif in notifications:
            try:
                success, error_msg = await _dispatch_send(
                    client,
                    notif.phone_number,
                    notif.content_text,
                )
            except Exception as exc:
                success   = False
                error_msg = f"Excepción inesperada en _dispatch_send: {exc}"
                log.error(error_msg)

            if success:
                notif.status    = NotificationStatus.SENT
                notif.error_log = None
                sent_count += 1

            else:
                notif.retry_count += 1
                notif.error_log    = error_msg

                if notif.retry_count >= notif.max_retries:
                    notif.status = NotificationStatus.FAILED
                    failed_count += 1
                    log.error(
                        "Notificación %s marcada como FAILED definitivo tras %d intentos. "
                        "Destino: %s | Error: %s",
                        notif.id, notif.retry_count, notif.phone_number, error_msg,
                    )
                else:
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
