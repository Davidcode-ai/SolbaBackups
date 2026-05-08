import logging
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)

# Configuraciones SMTP por defecto (Debe adaptarse al entorno del cliente)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# SMTP_USER = "tu-correo@gmail.com"
# SMTP_PASSWORD = "tu-contraseña-de-aplicacion"

def send_email_notification(to_email: str, subject: str, body: str):
    """
    Envía un correo electrónico mediante SMTP.
    NOTA: Requiere configurar SMTP_USER y SMTP_PASSWORD reales, o inyectarlos
    desde el entorno/configuración.
    """
    if not to_email:
        log.warning("No se proporcionó un email de destino. Se omite la notificación.")
        return

    log.info(f"📧 Preparando notificación para {to_email} con asunto: '{subject}'")
    
    # Descomentado: Intento de conexión SMTP Real para el test
    SMTP_USER = "tu-correo-aqui@gmail.com" # Dummy credentials para provocar el fallo real de handshake
    SMTP_PASSWORD = "password"
    
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = SMTP_USER
        msg['To'] = to_email

        # Establecer timeout para no dejar colgada la UI
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=5)
        server.starttls()
        # Esto provocará una excepción real de Autenticación
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        log.info(f"✅ Email enviado correctamente a {to_email}")
    except smtplib.SMTPAuthenticationError as e:
        log.error(f"❌ Error de Autenticación SMTP: {e.smtp_error.decode('utf-8')}")
        raise Exception(f"Autenticación SMTP fallida: {e.smtp_error.decode('utf-8')}")
    except Exception as e:
        log.error(f"❌ Error crítico de red o SMTP al enviar el email: {e}")
        raise Exception(f"Fallo de conexión SMTP ({SMTP_SERVER}:{SMTP_PORT}): {str(e)}")

