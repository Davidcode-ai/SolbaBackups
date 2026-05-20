"""
src/db/models.py — Modelos ORM de SQLAlchemy (Tablas de la BD).

Define el esquema completo de la base de datos SQLite de SolbaBackups.
Todas las clases heredan de ``Base`` (definida en ``database.py``).

Tablas:
    - ``Job``         : Configuración completa de un job de backup.
    - ``RunHistory``  : Registro de cada ejecución de un job.
    - ``LogEntry``    : Entradas de log individuales de cada ejecución.
    - ``AppSetting``  : Configuración global de la aplicación (clave-valor JSON).

Relaciones:
    - Job 1 → N RunHistory (cascade delete)
    - RunHistory 1 → N LogEntry (cascade delete)

Convenciones de nombres:
    - Tablas en snake_case plural: ``jobs``, ``run_history``, ``log_entries``.
    - Claves foráneas con sufijo ``_id``.
    - Timestamps en UTC (SQLite los guarda como TEXT en formato ISO 8601).
"""

import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class Job(Base):
    """
    Representa la configuración completa de un Job de backup.

    Un Job define QUÉ base de datos respaldar, CÓMO procesarla
    (compresión, encriptación) y DÓNDE guardar el resultado,
    así como CUÁNDO ejecutarse (schedule).

    Atributos de conexión (prefijo ``db_``):
        Almacenan los parámetros necesarios para conectarse al motor de BD.
        Las contraseñas se guardan encriptadas con Fernet.

    Atributos de destino (prefijo ``dest_``):
        Configuración del destino de almacenamiento.

    Atributos de schedule (prefijo ``schedule_``):
        Define la recurrencia del job compatible con APScheduler.
    """

    __tablename__ = "jobs"

    # ── Identificación ────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    # ── Conector de Base de Datos ─────────────────────────────────────────
    db_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="postgresql | mysql | sqlserver | sqlite | mdb | folder (copia con timestamp opcional) | sync (espejo 1:1 en dest_local_path)"
    )
    db_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    db_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    db_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    db_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    db_password: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Contraseña temporal en texto plano (MVP)"
    )
    db_password_enc: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Contraseña encriptada con Fernet (src.processors.encryptor)"
    )
    db_extra_params: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="JSON con parámetros adicionales del conector (ej. ssl_mode)"
    )

    # ── Procesadores ──────────────────────────────────────────────────────
    compress: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    compress_format: Mapped[str] = mapped_column(
        String(10), default="zip", nullable=False,
        comment="zip | gz"
    )
    encrypt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    encrypt_password: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Contraseña de encriptación en texto plano (MVP)"
    )
    encrypt_password_enc: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Contraseña de encriptación del backup, encriptada con Fernet"
    )

    # ── Destino ───────────────────────────────────────────────────────────
    dest_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="local",
        comment="local | google_drive"
    )
    dest_local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    dest_retention_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Días que se conservan los backups (null = sin límite)"
    )
    dest_gdrive_folder_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dest_gdrive_folder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dest_gdrive_credentials_json: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="JSON de credenciales OAuth2 de Google Drive"
    )
    
    # ── Schedule ──────────────────────────────────────────────────────────
    schedule_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="cron | interval | None (solo manual)"
    )
    schedule_cron: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Expresión cron (ej. '0 2 * * *' para las 2:00 AM diario)"
    )
    schedule_interval_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Intervalo en minutos si schedule_type == 'interval'"
    )
    schedule_next_run: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="Próxima ejecución programada (gestionado por APScheduler)"
    )

    # ── Relaciones ────────────────────────────────────────────────────────
    runs: Mapped[list["RunHistory"]] = relationship(
        "RunHistory",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def last_run_status(self) -> str | None:
        if not self.runs:
            return None
        # Sort runs by started_at descending and get the first one's status
        sorted_runs = sorted(self.runs, key=lambda r: r.started_at, reverse=True)
        return sorted_runs[0].status

    @property
    def source_local_path(self) -> str | None:
        """Origen local en disco para carpeta/sincronización (en el esquema actual, ``db_name``)."""
        return self.db_name


class RunHistory(Base):
    """
    Registro inmutable de cada ejecución de un Job de backup.

    Se crea al inicio de cada ejecución con ``status='running'`` y
    se actualiza al finalizar con el resultado y métricas.

    El campo ``status`` sigue una máquina de estados simple:
        running → success | failed | warning
    """

    __tablename__ = "run_history"

    # ── Identificación ────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Desnormalizado para no perder el nombre si el job se borra"
    )

    # ── Temporización ─────────────────────────────────────────────────────
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    duration_secs: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Resultado ─────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running",
        comment="running | success | failed | warning"
    )
    trigger: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual",
        comment="manual | scheduled"
    )
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    backup_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_url: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="URL/ruta donde quedó almacenado el backup"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relaciones ────────────────────────────────────────────────────────
    job: Mapped["Job"] = relationship("Job", back_populates="runs")
    log_entries: Mapped[list["LogEntry"]] = relationship(
        "LogEntry",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="select",
    )


class LogEntry(Base):
    """
    Entrada individual de log generada durante la ejecución de un Job.

    Cada evento significativo del pipeline (conectar, volcar, comprimir,
    encriptar, subir, limpiar) genera una entrada de log con su timestamp,
    nivel y mensaje descriptivo.

    Se insertan en tiempo real durante la ejecución para que el endpoint
    SSE pueda hacer polling y enviarlas al frontend.
    """

    __tablename__ = "log_entries"

    # ── Identificación ────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("run_history.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Contenido ─────────────────────────────────────────────────────────
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    level: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="DEBUG | INFO | WARNING | ERROR | CRITICAL"
    )
    stage: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="connect | dump | compress | encrypt | upload | cleanup | done"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Relaciones ────────────────────────────────────────────────────────
    run: Mapped["RunHistory"] = relationship("RunHistory", back_populates="log_entries")


class AppSetting(Base):
    """
    Configuración global de la aplicación almacenada como clave-valor.

    Permite guardar configuraciones diversas (SMTP, rutas de herramientas,
    retención por defecto, tema de la UI) sin necesidad de migraciones
    de esquema al añadir nuevas opciones.

    El campo ``value_json`` almacena el valor serializado como JSON, lo que
    permite guardar strings, números, listas o diccionarios anidados.

    Claves conocidas (documentadas, no exhaustivas):
        - ``smtp_host``, ``smtp_port``, ``smtp_user``, ``smtp_password_enc``
        - ``notify_on_failure``, ``notify_on_success``
        - ``pg_dump_path``, ``mysqldump_path``, ``sqlcmd_path``
        - ``log_retention_days``
        - ``ui_theme``: 'dark' | 'light'
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Valor serializado como JSON"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
