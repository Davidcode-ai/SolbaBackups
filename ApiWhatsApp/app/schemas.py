"""
app/schemas.py  –  Modelos de validación Pydantic (v2) para los endpoints de la API.
"""
import re
import uuid
from typing import Any
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
_PHONE_RE = re.compile(r"^\d{7,15}$")   # E.164 sin el '+': 7-15 dígitos


# ---------------------------------------------------------------------------
# Solicitud de notificación (entrada)
# ---------------------------------------------------------------------------
class NotificationRequest(BaseModel):
    """
    Payload que debe enviar el cliente (p. ej. SolbaBackups) para
    encolar un mensaje de WhatsApp.

    Ejemplo de body JSON:
    {
        "to": "34622430735",
        "template_name": "hello_world",
        "language_code": "en_US",
        "template_vars": []
    }
    """
    to: str = Field(
        ...,
        description="Número de teléfono del destinatario en formato E.164 sin '+' (ej: 34622430735).",
        examples=["34622430735"],
    )
    template_name: str = Field(
        default="hello_world",
        description="Nombre del template aprobado en Meta Business.",
        examples=["hello_world"],
    )
    language_code: str = Field(
        default="en_US",
        description="Código de idioma del template (ej: 'es_ES', 'en_US').",
        examples=["en_US", "es_ES"],
    )
    template_vars: list[Any] = Field(
        default_factory=list,
        description="Lista de variables de sustitución para el template (puede estar vacía).",
    )

    @field_validator("to")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip().lstrip("+")
        if not _PHONE_RE.match(v):
            raise ValueError(
                "El número de teléfono debe contener entre 7 y 15 dígitos "
                "en formato E.164 sin '+' (ej: 34622430735)."
            )
        return v

    @field_validator("template_name")
    @classmethod
    def validate_template_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre del template no puede estar vacío.")
        return v


# ---------------------------------------------------------------------------
# Respuestas (salida)
# ---------------------------------------------------------------------------
class NotificationResponse(BaseModel):
    """Respuesta devuelta al encolar un mensaje correctamente (HTTP 202)."""
    id: uuid.UUID
    status: str
    message: str


class HealthResponse(BaseModel):
    """Respuesta del endpoint de monitoreo /health."""
    status: str
    database: str
    version: str = "1.0.0"
