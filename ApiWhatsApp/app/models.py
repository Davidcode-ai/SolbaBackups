import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Enum, DateTime, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class NotificationStatus(enum.Enum):
    PENDING    = "PENDING"
    PROCESSING = "PROCESSING"
    SENT       = "SENT"
    FAILED     = "FAILED"


class WhatsAppNotification(Base):
    """
    Tabla del patrón Outbox para notificaciones WhatsApp.

    Estados del ciclo de vida:
        PENDING → PROCESSING → SENT
                             → FAILED (retry_count < max_retries → vuelve a PENDING)
                             → FAILED definitivo (retry_count >= max_retries)
    """
    __tablename__ = 'whatsapp_notifications'

    # ── Identificación ────────────────────────────────────────────────────
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Datos del mensaje ─────────────────────────────────────────────────
    phone_number  = Column(String(20), nullable=False, index=True)
    content_text  = Column(Text, nullable=False)
    source_system = Column(String(50), nullable=True,
                           comment="Sistema que insertó el mensaje (ej: SolbaBackups)")

    # ── Estado ───────────────────────────────────────────────────────────
    status = Column(
        Enum(NotificationStatus),
        default=NotificationStatus.PENDING,
        nullable=False,
    )

    # ── Control de reintentos ─────────────────────────────────────────────
    retry_count = Column(Integer, default=0, nullable=False,
                         comment="Número de intentos de envío realizados")
    max_retries = Column(Integer, default=3, nullable=False,
                         comment="Máximo de reintentos antes de FAILED definitivo")

    # ── Auditoría ─────────────────────────────────────────────────────────
    error_log    = Column(Text, nullable=True)
    created_at   = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # ── Índice Parcial ───────────────────────────────────────────────────
    # Solo indexa filas PENDING → reduce tamaño del índice y acelera al worker.
    # CORRECCIÓN: se usa NotificationStatus.PENDING (no el string 'PENDING')
    # para que SQLAlchemy genere la cláusula WHERE correcta.
    __table_args__ = (
        Index(
            'idx_pending_notifications',
            'status',
            postgresql_where=(
                Column('status', Enum(NotificationStatus)) == NotificationStatus.PENDING
            ),
        ),
    )
