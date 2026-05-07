import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Importamos tu router de jobs
from src.api.routers import jobs

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Aquí irá la lógica de arranque del Scheduler más adelante
    yield
    # Aquí irá la lógica de apagado


def create_app(frontend_path: Path | None = None) -> FastAPI:
    """Fábrica que construye la aplicación FastAPI."""
    app = FastAPI(title="SolbaBackups API", lifespan=lifespan)

    # 1. Registramos las rutas de la API primero
    _register_routers(app)

    # 2. Calculamos la ruta del Frontend
    if frontend_path is None:
        base_dir = Path(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        frontend_path = base_dir / "src" / "frontend"

    # 3. Montamos el Frontend estático
    _mount_frontend(app, frontend_path)

    return app


def _register_routers(app: FastAPI) -> None:
    """Registra los endpoints de la API."""
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(history.router, prefix="/api/v1")

def _mount_frontend(app: FastAPI, frontend_path: Path) -> None:
    """Monta el HTML y JS."""
    if frontend_path.exists():
        app.mount(
            "/", StaticFiles(directory=str(frontend_path), html=True), name="frontend"
        )
    else:
        print(f"⚠️ CUIDADO: No se encontró la carpeta del frontend en: {frontend_path}")


# Creamos la instancia por defecto para Uvicorn
app = create_app()
