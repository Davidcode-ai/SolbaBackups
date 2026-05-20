import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg.set_content('Contraseña: ñ')
msg['Subject'] = 'Notificación de prueba ñ'
msg['From'] = 'test@example.com'
msg['To'] = 'test@example.com'
print(msg.as_string())
