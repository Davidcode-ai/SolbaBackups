import asyncio
import os
import uuid
import ssl
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import insert

# Importamos el modelo y el estado
from app.models import WhatsAppNotification, NotificationStatus

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

async def send_test():
    if not DATABASE_URL:
        print("❌ Error: No se encontró DATABASE_URL en el .env")
        return

    # IMPORTANTE: Cambia este número por el tuyo para la prueba
    # Debe ir con prefijo de país y sin el '+' (ej: 34600112233)
    target_phone = "34622430735" 
    
    print(f"--- Prueba de Notificación WhatsApp ---")
    print(f"Conectando a la base de datos...")
    
    # Configuramos motor (usamos los mismos argumentos que en database.py para SSL)
    _connect_args = {
        "statement_cache_size": 0  # Desactivar caché de sentencias (vital para Supabase Pooler)
    }
    
    if "supabase.co" in DATABASE_URL or "supabase.com" in DATABASE_URL:
        _ssl_ctx = ssl.create_default_context()
        _ssl_ctx.check_hostname = False
        _ssl_ctx.verify_mode = ssl.CERT_NONE
        _connect_args["ssl"] = _ssl_ctx

    engine = create_async_engine(
        DATABASE_URL, 
        connect_args=_connect_args
    )
    
    async with engine.begin() as conn:
        print(f"Insertando mensaje de prueba para: {target_phone}...")
        
        stmt = insert(WhatsAppNotification).values(
            id=uuid.uuid4(),
            phone_number=target_phone,
            content_text="🚀 *¡Prueba de ApiWhatsApp Exitosa!*\nEste es un mensaje de prueba enviado desde tu nuevo sistema de notificaciones outbox.",
            source_system="PruebaManual",
            status=NotificationStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        await conn.execute(stmt)
    
    print(f"[OK] ¡Mensaje insertado en Supabase!")
    print(f"Ahora asegúrate de tener ejecutando: python -m app.main")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(send_test())
