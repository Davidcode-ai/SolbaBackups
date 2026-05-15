import logging
from datetime import timedelta, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, func, select
from app.models import WhatsAppNotification, NotificationStatus

log = logging.getLogger(__name__)


async def recover_orphaned_notifications(db_session: AsyncSession) -> None:
    """
    Sweeper — recupera mensajes atascados en estado PROCESSING.

    Un mensaje huérfano es aquel que lleva más de 5 minutos en PROCESSING
    sin haber terminado (posiblemente por un crash del worker o un timeout
    de red no capturado).

    Acción:
        - Devuelve el mensaje a PENDING para que el worker lo reintente.
        - Limpia processed_at para que el timestamp sea coherente.
        - Incrementa retry_count para reflejar que este intento no terminó bien.
        - Si retry_count >= max_retries, lo marca como FAILED definitivamente.
    """
    threshold_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    # ── Paso 1: Contar cuántos mensajes huérfanos hay (para logging) ──────
    count_stmt = (
        select(func.count())
        .select_from(WhatsAppNotification)
        .where(
            (WhatsAppNotification.status == NotificationStatus.PROCESSING)
            & (WhatsAppNotification.processed_at < threshold_time)
        )
    )
    count_result = await db_session.execute(count_stmt)
    orphan_count = count_result.scalar_one()

    if orphan_count == 0:
        log.debug("Sweeper: no hay mensajes huérfanos que recuperar.")
        return

    log.warning(
        "Sweeper: se encontraron %d mensaje(s) huérfano(s) en PROCESSING "
        "desde hace más de 5 minutos. Recuperando...",
        orphan_count,
    )

    # ── Paso 2: Recuperar los que aún tienen reintentos disponibles ───────
    recover_stmt = (
        update(WhatsAppNotification)
        .where(
            (WhatsAppNotification.status == NotificationStatus.PROCESSING)
            & (WhatsAppNotification.processed_at < threshold_time)
            & (WhatsAppNotification.retry_count < WhatsAppNotification.max_retries)
        )
        .values(
            status=NotificationStatus.PENDING,
            processed_at=None,
            retry_count=WhatsAppNotification.retry_count + 1,
            error_log="Recuperado por el Sweeper: el worker no completó el envío a tiempo.",
        )
    )
    await db_session.execute(recover_stmt)

    # ── Paso 3: Marcar como FAILED los que agotaron sus reintentos ────────
    fail_stmt = (
        update(WhatsAppNotification)
        .where(
            (WhatsAppNotification.status == NotificationStatus.PROCESSING)
            & (WhatsAppNotification.processed_at < threshold_time)
            & (WhatsAppNotification.retry_count >= WhatsAppNotification.max_retries)
        )
        .values(
            status=NotificationStatus.FAILED,
            error_log=(
                "Marcado como FAILED por el Sweeper: "
                "máximo de reintentos alcanzado sin completar el envío."
            ),
        )
    )
    await db_session.execute(fail_stmt)

    await db_session.commit()

    log.info(
        "Sweeper completado: %d mensaje(s) huérfano(s) procesados.",
        orphan_count,
    )
