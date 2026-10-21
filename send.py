import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==============================================================================
# CONFIGURACIÓN: Introduce aquí tu correo real de Gmail y tu Contraseña de Aplicación
# (Generada desde la sección de seguridad de tu cuenta de Google)
# ==============================================================================
SENDER_EMAIL = "tu-correo-real@gmail.com"       
SENDER_PASSWORD = "tu-contraseña-de-aplicacion"  # Contraseña de 16 caracteres de Google

def send_real_gmail(receiver_email, code):
    """Envía el código de verificación de 6 dígitos mediante el servidor SMTP de Gmail"""
    try:
        # Configurar el mensaje
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = "Código de Verificación - AfricanWorld"
        
        body = f"""¡Hola!

Gracias por registrarte en AfricanWorld. Tu código de verificación es:

{code}

Este código expira en 2 minutos. Si no solicitaste esta cuenta, ignora este mensaje.

Atentamente,
El equipo de AfricanWorld
"""
        msg.attach(MIMEText(body, 'plain'))

        # Conexión al servidor SMTP de Google con TLS (Puerto 587)
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        
        print(f"[ÉXITO] Correo de verificación enviado correctamente a {receiver_email}")
        return True
        
    except Exception as e:
        print(f"[ERROR SMTP] No se pudo enviar el correo a {receiver_email}. Detalle: {e}")
        return False