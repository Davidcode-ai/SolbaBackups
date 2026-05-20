"""
src/core/db_credentials.py — Resolución segura de contraseñas de jobs.

Centraliza la lógica para obtener contraseñas de conexión a BD desde el
payload de la API o desde un job persistido (modo edición).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.db import crud

log = logging.getLogger(__name__)


def resolve_job_db_password(
    password: str | None,
    job_id: int | None,
    db: Session,
) -> str:
    """
    Devuelve la contraseña en texto plano para conectar a una BD.

    Prioridad:
        1. Contraseña enviada en el request (no vacía).
        2. ``db_password`` del job en BD (por ``job_id``).
        3. ``db_password_enc`` desencriptada si hay clave maestra configurada.

    Args:
        password: Valor del campo password del request (puede ser vacío).
        job_id: ID del job en modo edición (opcional).
        db: Sesión SQLAlchemy activa.

    Returns:
        str: Contraseña resuelta, o cadena vacía si no hay ninguna disponible.
    """
    plain = (password or "").strip()
    if plain:
        return plain

    if job_id is None:
        return ""

    job = crud.job_get_by_id(db, job_id)
    if not job:
        return ""

    stored = getattr(job, "db_password", None)
    if stored and str(stored).strip():
        return str(stored).strip()

    enc = getattr(job, "db_password_enc", None)
    if enc and str(enc).strip():
        try:
            from src.config.settings import Settings
            from src.processors.encryptor import Encryptor

            settings = Settings()
            key_raw = (settings._config.get("encryption_key") or "").strip()
            if key_raw:
                decrypted = Encryptor.decrypt_field(
                    str(enc).strip(), key_raw.encode("utf-8")
                )
                if decrypted and str(decrypted).strip():
                    return str(decrypted).strip()
        except Exception as exc:
            log.debug("No se pudo desencriptar db_password_enc del job %s: %s", job_id, exc)

    return ""
