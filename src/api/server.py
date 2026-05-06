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
    """Gestor de ciclo de vida de FastAPI."""
    # --- STARTUP ---
    # 1. Inicializar Base de Datos (crear tablas si no existen)
    from src.db.database import init_db
    init_db()

    # 2. Instanciar e Iniciar Lógica Core y Scheduler
    from src.core.job_manager import JobManager
    from src.core.job_scheduler import JobScheduler
    
    app.state.job_manager = JobManager()
    app.state.scheduler = JobScheduler(app.state.job_manager)
    
    # Iniciar el proceso en background y cargar los jobs de la BD
    app.state.scheduler.start()
    app.state.scheduler.load_jobs_from_db()

    yield  # La aplicación FastAPI está funcionando
    
    # --- SHUTDOWN ---
    # Apagar el scheduler limpiamente al cerrar el servidor
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.stop()


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
