"""
app/main.py  –  Punto de entrada del servidor FastAPI (ApiWhatsApp).

Arquitectura:
  - FastAPI como servidor web asíncrono (expuesto con Uvicorn).
  - APScheduler corriendo en segundo plano (via lifespan) con dos jobs:
      · Worker  → cada 1s   → lee PENDING y envía a Meta Cloud API.
      · Sweeper → cada 5min → rescata mensajes huérfanos (PROCESSING > 5min).
  - Patrón Transactional Outbox: desacopla la API REST del envío real a Meta,
    lo que garantiza que una lentitud de Meta no bloquea al cliente.

Arranque en desarrollo:
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Arranque en producción:
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine, Base, AsyncSessionLocal, get_db
from app.core.scheduler import create_scheduler
from app.routes.notifications import router as notifications_router
from app.schemas import HealthResponse


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: arranque y apagado ordenado
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gestiona el ciclo de vida del servidor:
    - STARTUP : Crea tablas en BD + arranca el scheduler en segundo plano.
    - SHUTDOWN: Apaga el scheduler limpiamente + cierra el pool de conexiones.
    """
    # ── Startup ───────────────────────────────────────────────────────────
    log.info("Iniciando ApiWhatsApp (FastAPI + Outbox Worker)...")

    # Crear tablas si no existen
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Base de datos inicializada correctamente.")

    # Arrancar el scheduler (worker + sweeper) en segundo plano
    scheduler = create_scheduler()
    scheduler.start()
    log.info("Scheduler iniciado. Worker: cada 1s | Sweeper: cada 5min.")

    # Guardamos referencia para poder pararlo en el shutdown
    app.state.scheduler = scheduler

    yield  # ← El servidor atiende peticiones mientras está aquí

    # ── Shutdown ──────────────────────────────────────────────────────────
    log.info("Apagando ApiWhatsApp...")
    scheduler.shutdown(wait=True)
    log.info("Scheduler detenido.")
    await engine.dispose()
    log.info("Pool de conexiones cerrado. Hasta pronto!")


# ---------------------------------------------------------------------------
# Aplicación FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ApiWhatsApp – Solba Informática",
    description=(
        "API REST asíncrona para el envío de notificaciones WhatsApp mediante "
        "el patrón Transactional Outbox. Diseñada para integrarse con SolbaBackups "
        "y otros sistemas internos de Solba Informática."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (ajustar origins en producción) ──────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restringir a IPs internas en producción
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
app.include_router(notifications_router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Sistema"],
    summary="Health Check",
    description="Verifica que el servidor y la conexión a PostgreSQL están operativos.",
)
async def health_check() -> HealthResponse:
    """
    Endpoint de monitoreo para sistemas como Uptime Robot, Datadog, etc.
    Comprueba activamente que la conexión a la base de datos responde.
    """
    db_status = "disconnected"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        log.error("Health check — fallo de BD: %s", exc)

    return HealthResponse(status="online", database=db_status)


@app.get("/", tags=["Sistema"], include_in_schema=False)
async def root() -> dict:
    return {
        "service": "ApiWhatsApp – Solba Informática",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
