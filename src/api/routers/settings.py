"""
src/api/routers/settings.py — Endpoints para configuración global.
"""

import os
import sys
from fastapi import APIRouter, Depends
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from typing import Any

from src.core import models
from src.db import crud
from src.db.database import get_db

router = APIRouter(prefix="/settings", tags=["Settings"])


def _get_base_path() -> str:
    """
    Devuelve la carpeta base donde vive el .env:
    - Modo frozen (PyInstaller): directorio del .exe
    - Modo desarrollo: raíz del proyecto (4 niveles arriba de este archivo)
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # src/api/routers/settings.py  →  ../../.. = raíz del proyecto
    return os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
    )


def _get_env_path() -> str:
    """Devuelve la ruta absoluta al archivo .env, independiente del CWD."""
    return os.path.join(_get_base_path(), '.env')

@router.get("", response_model=models.AppSettingsRead)
def get_settings(db: Session = Depends(get_db)):
    """
    Devuelve todas las variables de configuración global guardadas en la BD.
    Incluye flags derivados del entorno (p. ej. WhatsApp) para la UI/onboarding.
    """
    settings_dict = crud.setting_get_all(db)
    env_path = _get_env_path()
    load_dotenv(dotenv_path=env_path, override=False)
    phone = (os.getenv("WHATSAPP_PHONE") or "").strip()
    wa_enabled = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
    settings_dict["whatsapp_runtime_configured"] = bool(phone and wa_enabled)
    return {"settings": settings_dict}

@router.put("", response_model=models.AppSettingsRead)
def update_settings(settings_in: models.AppSettingsUpdate, db: Session = Depends(get_db)):
    """
    Actualiza o crea variables de configuración global.
    Acepta tanto JSON anidado en {"settings": {...}} como JSON plano {"key": "value"}.
    """
    # Extraemos todos los campos, incluyendo los "extra" del JSON plano
    data = settings_in.model_dump(exclude_unset=True)
    # Extraemos el dict 'settings' si viene
    settings_dict = data.pop("settings", {}) or {}
    # Juntamos todo
    settings_dict.update(data)

    crud.setting_set_many(db, settings_dict)
    updated_settings = crud.setting_get_all(db)
    return {"settings": updated_settings}


@router.post("/test-email")
def test_email(db: Session = Depends(get_db)):
    """
    Envía un correo de prueba al correo de notificaciones configurado.
    Devuelve errores estructurados con el tipo de fallo para que el
    frontend pueda mostrar una solución concreta al usuario.
    """
    from fastapi import HTTPException
    from dotenv import load_dotenv
    from src.core.notifications import (
        send_email_notification,
        SmtpNotConfiguredError,
        SmtpAuthError,
        SmtpConnectionError,
    )

    # Cargar el .env desde la ruta absoluta (no desde el CWD)
    env_path = _get_env_path()
    load_dotenv(dotenv_path=env_path, override=True)

    smtp_host = (os.getenv("SOLBA_SMTP_HOST") or "").strip()
    smtp_port = (os.getenv("SOLBA_SMTP_PORT") or "").strip()
    smtp_user = (os.getenv("SOLBA_SMTP_USER") or "").strip()
    smtp_pass = (os.getenv("SOLBA_SMTP_PASS") or "").strip()
    if not smtp_host or not smtp_port or not smtp_user or not smtp_pass:
        raise HTTPException(
            status_code=400,
            detail="Faltan las credenciales SMTP en el archivo .env",
        )

    settings = crud.setting_get_all(db)
    notification_email = settings.get("notification_email")
    
    if not notification_email:
        raise HTTPException(
            status_code=400,
            detail={
                "error_type": "no_recipient",
                "message": "No hay correo de destino configurado.",
                "action": "Ve a Ajustes → General e introduce un email en el campo «Correo para recibir alertas»."
            }
        )
        
    try:
        send_email_notification(
            to_email=notification_email,
            subject="🔔 SolbaBackups: Prueba de Notificaciones",
            body=(
                "¡Hola!\n\n"
                "Este es un correo de prueba generado automáticamente por SolbaBackups.\n"
                "Si lo recibes, las notificaciones están funcionando correctamente.\n\n"
                "— Equipo Solba"
            )
        )
        return {"success": True, "message": f"✅ Correo enviado correctamente a {notification_email}"}

    except SmtpNotConfiguredError as e:
        raise HTTPException(status_code=503, detail={
            "error_type": "smtp_not_configured",
            "message": str(e),
            "action": "Verifica que el archivo .env tenga SOLBA_SMTP_HOST y SOLBA_SMTP_PORT configurados."
        })
    except SmtpAuthError as e:
        raise HTTPException(status_code=401, detail={
            "error_type": "smtp_auth",
            "message": str(e),
            "action": "Verifica SOLBA_SMTP_USER y SOLBA_SMTP_PASS en el archivo .env."
        })
    except SmtpConnectionError as e:
        raise HTTPException(status_code=502, detail={
            "error_type": "smtp_connection",
            "message": str(e),
            "action": "Comprueba que el host SMTP y el puerto sean correctos y que el servidor sea accesible."
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error_type": "unknown",
            "message": f"Error inesperado: {str(e)}",
            "action": "Revisa los logs del servidor para más detalles."
        })

