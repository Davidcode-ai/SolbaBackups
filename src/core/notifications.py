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
from __future__ import annotations

import html
import logging
import os
import smtplib
import socket
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

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
    """Load SMTP settings from environment (``.env`` / process env).

    Reads ``SOLBA_SMTP_HOST``, ``SOLBA_SMTP_USER``, ``SOLBA_SMTP_PASS``, and
    ``SOLBA_SMTP_PORT``. Missing credentials yield ``configured: False`` and a
    no-op send path.

    Returns:
        Dict with keys: ``host``, ``port``, ``user``, ``password``,
        ``configured`` (bool), and ``source`` (``\"env\"`` or ``\"none\"``).

    Note:
        Invalid ``SOLBA_SMTP_PORT`` falls back to ``587``.
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
# Plantilla HTML (backup) — CSS inline para compatibilidad con clientes de correo
# ──────────────────────────────────────────────────────────────────────────────

def format_bytes_display(num_bytes: int | None) -> str:
    """Format a byte count as a human-readable IEC string.

    Args:
        num_bytes: Size in bytes, or ``None`` if unknown.

    Returns:
        String like ``\"1.50 MiB\"`` or ``\"N/D\"`` when ``num_bytes`` is ``None``.
    """
    if num_bytes is None:
        return "N/D"
    n = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{int(num_bytes)} B"


def render_backup_report_html(
    *,
    success: bool,
    job_name: str,
    job_id: int,
    db_type: str,
    destination_summary: str,
    log_lines: list[str],
    error_message: str | None = None,
    size_display: str | None = None,
) -> str:
    """Build an HTML email body for a backup report (inline CSS, corporate layout).

    Escapes all dynamic fragments for safe inclusion in HTML email clients.

    Args:
        success: Whether the job completed successfully (badge + title).
        job_name: Display name of the job.
        job_id: Numeric job id shown in the details table.
        db_type: Engine or task type label.
        destination_summary: Short destination description (path or Drive).
        log_lines: Log lines rendered inside a styled ``<pre>`` block.
        error_message: Optional failure detail (escaped).
        size_display: Pre-formatted size string (e.g. from :func:`format_bytes_display`).

    Returns:
        Full HTML document as a single string (UTF-8).

    Note:
        Badge and heading copy are Spanish for product consistency with the UI.
    """
    safe_name = html.escape(job_name or "")
    safe_motor = html.escape(str(db_type or "N/D"))
    safe_dest = html.escape(str(destination_summary or "N/D"))
    safe_size = html.escape(size_display or "N/D")
    badge_bg = "#22c55e" if success else "#ef4444"
    badge_text = "Exitoso" if success else "Fallido"
    status_title = "Copia finalizada correctamente" if success else "La tarea ha fallado"

    if error_message:
        err_block = (
            f'<p style="margin:16px 0 0 0;font-size:14px;line-height:1.5;color:#991b1b;">'
            f"<strong>Detalle:</strong> {html.escape(error_message)}</p>"
        )
    else:
        err_block = ""

    logs_joined = "\n".join(log_lines) if log_lines else "(No hay entradas de log)"
    safe_logs = html.escape(logs_joined)

    return f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f1f5f9;padding:28px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:640px;border-collapse:separate;border-spacing:0;background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 8px 24px rgba(15,23,42,0.08);">
          <tr>
            <td style="background-color:#1e293b;padding:20px 24px;">
              <span style="font-size:20px;font-weight:700;letter-spacing:0.02em;color:#ffffff;">SolbaBackups</span>
            </td>
          </tr>
          <tr>
            <td style="background-color:#ffffff;padding:24px 24px 16px 24px;">
              <span style="display:inline-block;padding:6px 14px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:0.05em;color:#ffffff;background-color:{badge_bg};">{badge_text}</span>
              <h1 style="margin:16px 0 0 0;font-size:18px;font-weight:600;color:#0f172a;">{html.escape(status_title)}</h1>
              {err_block}
            </td>
          </tr>
          <tr>
            <td style="background-color:#ffffff;padding:0 24px 20px 24px;">
              <p style="margin:0 0 12px 0;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#64748b;">Detalles</p>
              <table role="presentation" width="100%" style="border-collapse:collapse;font-size:14px;color:#334155;">
                <tr><td style="padding:8px 0;border-bottom:1px solid #e2e8f0;width:140px;color:#64748b;">Job</td><td style="padding:8px 0;border-bottom:1px solid #e2e8f0;"><strong>{safe_name}</strong> <span style="color:#94a3b8;">(ID {job_id})</span></td></tr>
                <tr><td style="padding:8px 0;border-bottom:1px solid #e2e8f0;color:#64748b;">Motor</td><td style="padding:8px 0;border-bottom:1px solid #e2e8f0;">{safe_motor}</td></tr>
                <tr><td style="padding:8px 0;border-bottom:1px solid #e2e8f0;color:#64748b;">Destino</td><td style="padding:8px 0;border-bottom:1px solid #e2e8f0;">{safe_dest}</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;">Tamaño</td><td style="padding:8px 0;">{safe_size}</td></tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background-color:#ffffff;padding:0 24px 28px 24px;">
              <p style="margin:0 0 8px 0;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#64748b;">Logs</p>
              <pre style="margin:0;padding:16px;background-color:#0f172a;color:#4ade80;border-radius:8px;font-size:11px;line-height:1.45;overflow:auto;max-height:320px;font-family:ui-monospace,Consolas,'Courier New',monospace;white-space:pre-wrap;word-break:break-word;">{safe_logs}</pre>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ──────────────────────────────────────────────────────────────────────────────
# Función pública de envío
# ──────────────────────────────────────────────────────────────────────────────

def send_email_notification(
    to_email: str,
    subject: str,
    body: str,
    *,
    html_body: str | None = None,
) -> None:
    """Send email via configured SMTP (TLS on port 587 or SSL on 465).

    When ``html_body`` is set, builds ``multipart/alternative`` with plain and
    HTML parts. If SMTP is not configured, logs and returns without raising.

    Args:
        to_email: Recipient address; empty skips send.
        subject: Message subject.
        body: Plain-text fallback body.
        html_body: Optional HTML part for rich clients.

    Returns:
        ``None``.

    Raises:
        SmtpAuthError: SMTP authentication failed.
        SmtpConnectionError: Network, TLS, or generic SMTP errors after connect.

    Note:
        Does **not** raise when credentials are missing; that path is a no-op.
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

    if html_body:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg["user"]
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain", "utf-8"))
        html_part = MIMEText(html_body, "html", "utf-8")
        msg.attach(html_part)
    else:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg["user"]
        msg["To"] = to_email
        msg.set_content(body, charset="utf-8")

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
