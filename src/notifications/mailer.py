"""
src/notifications/mailer.py — Sistema de Notificaciones por Correo Electrónico (SMTP)

Envía alertas a los administradores en caso de fallos en el sistema de backup.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

log = logging.getLogger(__name__)

import os

class EmailNotifier:
    """Gestor para envío de correos electrónicos vía SMTP."""

    def __init__(self, to_email: str):
        self.host = os.getenv("SOLBA_SMTP_HOST", "smtp.gmail.com")
        
        try:
            self.port = int(os.getenv("SOLBA_SMTP_PORT", "587"))
        except ValueError:
            self.port = 587
            
        self.user = os.getenv("SOLBA_SMTP_USER", "noreply.solbabackups@gmail.com")
        self.password = os.getenv("SOLBA_SMTP_PASS", "dummy_password_for_testing")
        self.to_email = to_email

    async def send_failure_alert(self, job_name: str, error_message: str, logs: str = "") -> bool:
        """
        Envía un correo de alerta en formato HTML cuando un backup falla.
        
        Args:
            job_name: Nombre del job que ha fallado.
            error_message: Razón o mensaje de error de la excepción.
            logs: Información adicional o logs (opcional).
            
        Returns:
            bool: True si se envió correctamente, False en caso contrario.
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🚨 [SolbaBackups] ALERTA: Fallo en el Job '{job_name}'"
            msg["From"] = self.user
            msg["To"] = self.to_email

            # Plantilla HTML básica
            html = f"""
            <html>
                <body style="font-family: Arial, sans-serif; color: #333;">
                    <div style="border: 1px solid #e11d48; padding: 20px; border-radius: 8px; background-color: #fff1f2;">
                        <h2 style="color: #e11d48; margin-top: 0;">❌ Alerta Crítica: Fallo de Backup</h2>
                        <p>El sistema automático ha detectado un error crítico al intentar ejecutar el backup.</p>
                        
                        <h4 style="margin-bottom: 5px;">Detalles del Job:</h4>
                        <p style="margin-top: 0;"><strong>Nombre:</strong> {job_name}</p>
                        
                        <h4 style="margin-bottom: 5px;">Mensaje de Error:</h4>
                        <div style="background: #fee2e2; padding: 10px; border-left: 4px solid #ef4444; font-family: monospace;">
                            {error_message}
                        </div>
                        
                        <br/>
                        <p style="font-size: 12px; color: #666;">
                            Este es un mensaje generado automáticamente por SolbaBackups. No responda a este correo.
                        </p>
                    </div>
                </body>
            </html>
            """
            
            part_html = MIMEText(html, "html")
            msg.attach(part_html)

            # Conexión SMTP
            # Dependiendo del puerto (465 para SSL directo, 587 para TLS)
            if self.port == 465:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=10)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=10)
                server.starttls()
                
            if self.password and self.password != "dummy_password_for_testing":
                server.login(self.user, self.password)
            else:
                log.warning("Saltando autenticación SMTP: contraseña no configurada o es la de pruebas.")
                
            server.send_message(msg)
            server.quit()
            
            log.info(f"✉️ Email de alerta enviado correctamente a {self.to_email} por el fallo en '{job_name}'.")
            return True
            
        except Exception as e:
            log.error(f"❌ Error interno enviando el email de notificación SMTP: {e}")
            return False
