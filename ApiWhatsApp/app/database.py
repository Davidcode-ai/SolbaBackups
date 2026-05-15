import os
import ssl
import logging
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

load_dotenv(override=True)

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no configurada.")

if not DATABASE_URL.startswith("postgresql+asyncpg://"):
    raise RuntimeError("Debe usar el driver postgresql+asyncpg://")

_parsed = urlparse(DATABASE_URL)
_host = _parsed.hostname or ""
_is_supabase = "supabase.co" in _host or "supabase.com" in _host

# Aquí es donde va la corrección: el argumento debe estar dentro de connect_args
_connect_args: dict = {
    "statement_cache_size": 0
}

if _is_supabase:
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE
    _connect_args["ssl"] = _ssl_ctx
    log.info("Supabase detectado — SSL activado.")

engine = create_async_engine(
    DATABASE_URL,
    echo=(os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"),
    connect_args=_connect_args, # Pasamos los argumentos aquí
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()
log.info("Motor de base de datos configurado correctamente.")


# ---------------------------------------------------------------------------
# Dependencia FastAPI: inyecta sesiones DB por petición
# ---------------------------------------------------------------------------
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Generador asíncrono para inyección de dependencias en FastAPI.
    Garantiza que la sesión se cierra correctamente al terminar la petición.
    """
    async with AsyncSessionLocal() as session:
        yield session
