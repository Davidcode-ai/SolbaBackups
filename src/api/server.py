from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
feature/integracion-frontend
import os

app = FastAPI(title="SolbaBackups API")

# Calculamos las rutas relativas basadas en la ubicación de este archivo (src/api/server.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIR = os.path.join(BASE_DIR, "src", "frontend")

# =====================================================================
# AQUÍ VAN LOS ROUTERS DE LA API (Endpoints)
# =====================================================================
# IMPORTANTE: Asegúrate de que los routers de la API se incluyan 
# ANTES de montar el directorio estático para que las rutas no choquen.
#
# Ejemplo de cómo incluiría los endpoints tu compañero:
# from src.api.routes import jobs_router
# app.include_router(jobs_router, prefix="/api/v1")


# =====================================================================
# MONTAJE DEL FRONTEND
# =====================================================================
# Montamos la carpeta src/frontend en la ruta raíz (/).
# El parámetro html=True permite que al acceder a "/" se sirva "index.html" automáticamente.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
=======

from src.api.routers import history, jobs, logs, settings

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestor de ciclo de vida asíncrono de la aplicación FastAPI.

    Se ejecuta en el arranque (código antes del ``yield``) y en el apagado
    (código después del ``yield``).

    Startup:
        1. Crea todas las tablas de la BD SQLite si no existen.
        2. Inicia el scheduler de APScheduler.
        3. Carga desde la BD todos los Jobs activos y los registra en el scheduler.

    Shutdown:
        1. Detiene el scheduler de forma ordenada (espera a que terminen
           los jobs en ejecución si ``wait=True``).
        2. Cierra el engine de SQLAlchemy.

    Args:
        app: Instancia de FastAPI que recibe el contexto de ciclo de vida.

    Yields:
        None: El control vuelve a FastAPI durante la ejecución normal.
    """
    pass


def create_app(frontend_path: Path | None = None) -> FastAPI:
    """
    Fábrica que construye y devuelve la instancia configurada de FastAPI.

    Patrón Application Factory: permite crear instancias independientes
    para producción y para los tests de integración.

    Args:
        frontend_path: Ruta absoluta al directorio ``frontend/`` con los
                       archivos estáticos de la SPA. Si es ``None``, se
                       resuelve automáticamente relativa a este módulo.
                       En un bundle de PyInstaller se pasa la ruta de
                       ``sys._MEIPASS``.

    Returns:
        FastAPI: Aplicación completamente configurada y lista para ser
                 servida por Uvicorn.
    """
    pass


def _register_routers(app: FastAPI) -> None:
    """
    Registra todos los APIRouter de la aplicación bajo el prefijo ``/api/v1``.

    Centraliza el registro de rutas para mantener ``create_app`` limpio.
    Añade también las etiquetas de OpenAPI para una documentación clara.

    Args:
        app: Instancia de FastAPI en la que registrar los routers.
    """
    app.include_router(jobs.router, prefix="/api/v1")
    # Cuando implementemos history, logs y settings, se añadirán aquí:
    # app.include_router(history.router, prefix="/api/v1")
    # app.include_router(logs.router, prefix="/api/v1")
    # app.include_router(settings.router, prefix="/api/v1")


def _mount_frontend(app: FastAPI, frontend_path: Path) -> None:
    """
    Monta los archivos estáticos del frontend en la ruta raíz de la app.

    Configura dos puntos de montaje:
        1. ``/assets`` → ``frontend/assets/`` para JS, CSS e imágenes.
        2. Un endpoint catch-all ``GET /`` que devuelve ``index.html``
           para que el router de la SPA vanilla JS funcione correctamente.

    Args:
        app: Instancia de FastAPI en la que montar los archivos.
        frontend_path: Ruta absoluta al directorio raíz del frontend.

    Raises:
        FileNotFoundError: Si el directorio ``frontend_path`` no existe.
    """
    pass
main
