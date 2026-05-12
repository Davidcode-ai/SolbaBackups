"""
src/core/notifications.py — Servicio de envío de notificaciones por email.

Jerarquía de configuración SMTP (de mayor a menor prioridad):
  1. Variables de entorno del sistema (.env) (SOLBA_SMTP_*)
  2. Configuración por defecto (sin credenciales → sólo warning en log)

Excepciones tipadas:
    - SmtpNotConfiguredError  : No hay SMTP configurado (ahora se maneja internamente como No-op).
  - SmtpAuthError           : Credenciales incorrectas.
  - SmtpConnectionError     : El servidor no es alcanzable / timeout.
"""
import logging
from dotenv import load_dotenv
import os
import smtplib
import socket
from email.message import EmailMessage

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Excepciones públicas tipadas
# ──────────────────────────────────────────────────────────────────────────────

class SmtpNotConfiguredError(Exception):
    """Se lanza cuando no existe ninguna configuración SMTP válida."""
    pass


class SmtpAuthError(Exception):
    """Se lanza cuando el servidor rechaza las credenciales."""
    pass


class SmtpConnectionError(Exception):
    """Se lanza cuando el servidor no es alcanzable (red, timeout, TLS…)."""
    pass


# ──────────────────────────────────────────────────────────────────────────────
# Resolución de credenciales SMTP
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_smtp_config() -> dict:
    """
    Devuelve un dict con las credenciales SMTP leyendo desde el archivo .env.

    Returns:
        dict con claves: host, port, user, password, configured (bool).
    """
    load_dotenv()
    
    host = os.getenv("SOLBA_SMTP_HOST", "").strip()
    user = os.getenv("SOLBA_SMTP_USER", "").strip()
    password = os.getenv("SOLBA_SMTP_PASS", "").strip()
    try:
        port = int(os.getenv("SOLBA_SMTP_PORT", "587"))
    except ValueError:
        port = 587

    if host and user and password:
        log.debug("📬 SMTP: usando variables de entorno del sistema (.env).")
        return {"host": host, "port": port, "user": user,
                "password": password, "configured": True, "source": "env"}

    # Sin configuración válida
    return {"host": host or "smtp.gmail.com", "port": port, "user": user,
            "password": "", "configured": False, "source": "none"}


# ──────────────────────────────────────────────────────────────────────────────
# Función pública de envío
# ──────────────────────────────────────────────────────────────────────────────

def send_email_notification(to_email: str, subject: str, body: str) -> None:
    """
    Envía un correo electrónico.

    Args:
        to_email:  Destinatario.
        subject:   Asunto del mensaje.
        body:      Cuerpo en texto plano.

    Raises:
        SmtpNotConfiguredError: No hay configuración SMTP disponible.
        SmtpAuthError:          Credenciales rechazadas por el servidor.
        SmtpConnectionError:    El servidor no es alcanzable.
    """
    if not to_email:
        log.warning("📧 Sin email de destino — notificación omitida.")
        return

    cfg = _resolve_smtp_config()

    if not cfg["configured"]:
        log.warning("Credenciales SMTP no configuradas. El correo no se enviará.")
        return

    log.info(
        f"📧 Enviando notificación a «{to_email}» "
        f"(via {cfg['host']}:{cfg['port']}, fuente: {cfg['source']})"
    )

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"]    = cfg["user"]
    msg["To"]      = to_email

    try:
        if cfg["port"] == 465:
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=8)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=8)
            server.starttls()

        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
        server.quit()
        log.info(f"✅ Email enviado correctamente a «{to_email}».")

    except smtplib.SMTPAuthenticationError as exc:
        raw = exc.smtp_error
        detail = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        log.error(f"❌ Autenticación SMTP fallida: {detail}")
        raise SmtpAuthError(
            f"Credenciales incorrectas para {cfg['user']}@{cfg['host']}. "
            f"Verifica SOLBA_SMTP_USER y SOLBA_SMTP_PASS en el archivo .env. "
            f"Detalle del servidor: {detail}"
        ) from exc

    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,
            socket.timeout, ConnectionRefusedError, OSError) as exc:
        log.error(f"❌ Error de conexión SMTP a {cfg['host']}:{cfg['port']}: {exc}")
        raise SmtpConnectionError(
            f"No se pudo conectar al servidor SMTP «{cfg['host']}:{cfg['port']}». "
            f"Comprueba que el host y puerto sean correctos y que no haya un "
            f"cortafuegos bloqueando la conexión. Detalle: {exc}"
        ) from exc

    except smtplib.SMTPException as exc:
        log.error(f"❌ Error SMTP genérico: {exc}")
        raise SmtpConnectionError(
            f"Error SMTP inesperado al enviar a «{to_email}»: {exc}"
        ) from exc
