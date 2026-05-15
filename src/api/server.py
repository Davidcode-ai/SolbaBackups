import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

# Importamos los routers de la API
from src.api.routers import jobs, history, settings, auth, stats, utils

log = logging.getLogger(__name__)


def add_validation_handler(app: FastAPI):
    """
    Agrega un manejador de excepciones personalizado para los errores de validación de Pydantic.

    Captura las excepciones RequestValidationError (HTTP 422) y las imprime en consola
    con un formato detallado, incluyendo la ruta, los errores específicos y el payload
    recibido, facilitando la depuración.

    Args:
        app (FastAPI): La instancia de la aplicación FastAPI a la que se le añadirá el manejador.

    Returns:
        None
    """
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        print("\n\n=== ERROR 422 UNPROCESSABLE ENTITY ===")
        print(f"Ruta: {request.method} {request.url}")
        print("Errores detallados de Pydantic:")
        for error in exc.errors():
            print(f"- {error['loc']}: {error['msg']}")
        
        try:
            # Intentamos leer el payload como JSON para imprimirlo claramente
            body = await request.json()
            print("Payload JSON recibido:")
            print(body)
        except Exception:
            # Si falla, leemos el cuerpo crudo (útil si el formato es completamente inválido)
            body = await request.body()
            print("Payload Crudo recibido:")
            print(body)
        print("======================================\n\n")
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "body": exc.body},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestor del ciclo de vida de la aplicación FastAPI.

    Se encarga de ejecutar lógica de inicialización antes de que la aplicación
    comience a recibir peticiones (startup) y lógica de limpieza antes de que
    la aplicación se detenga (shutdown).

    Args:
        app (FastAPI): La instancia de la aplicación FastAPI.

    Yields:
        None: Suspende la ejecución mientras la aplicación está en funcionamiento.
    """
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
    # para evitar hilos huérfanos o ejecuciones corruptas
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.stop()


def create_app(frontend_path: Path | None = None) -> FastAPI:
    """
    Fábrica que construye y configura la aplicación FastAPI.

    Inicializa la instancia de FastAPI, configura los manejadores de excepciones,
    registra los enrutadores (routers) de la API y monta los archivos estáticos
    del frontend.

    Args:
        frontend_path (Path | None, opcional): Ruta absoluta al directorio del
            frontend. Si es None, se calcula dinámicamente basándose en la
            ubicación de este archivo. Por defecto es None.

    Returns:
        FastAPI: La aplicación FastAPI configurada y lista para ejecutarse.
    """
    app = FastAPI(title="SolbaBackups API", lifespan=lifespan)

    # Añadimos el handler temporal para debuggear el 422
    add_validation_handler(app)

    # 1. Registramos las rutas de la API primero
    _register_routers(app)

    # 2. Calculamos la ruta del Frontend
    # Si no se provee una ruta, navegamos hacia arriba en el árbol de directorios
    # desde la ubicación actual (src/api/server.py -> src/api -> src -> raíz)
    if frontend_path is None:
        base_dir = Path(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        frontend_path = base_dir / "src" / "frontend"

    # 3. Montamos el Frontend estático
    _mount_frontend(app, frontend_path)

    return app


def _register_routers(app: FastAPI) -> None:
    """
    Registra los enrutadores (routers) de la API en la aplicación principal.

    Agrupa y monta bajo el prefijo '/api/v1' los distintos módulos de la API,
    además de registrar las rutas de autenticación e imprimir en consola el
    mapa de rutas registradas con fines de depuración.

    Args:
        app (FastAPI): La instancia de la aplicación FastAPI.

    Returns:
        None
    """
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(history.router, prefix="/api/v1")
    app.include_router(settings.router, prefix="/api/v1")
    app.include_router(stats.router, prefix="/api/v1")
    app.include_router(utils.router, prefix="/api/v1")
    app.include_router(auth.router)
    
    # Debug: Imprimir rutas registradas
    print("\n=== RUTAS REGISTRADAS ===")
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            methods = list(route.methods) if route.methods else []
            if 'GET' in methods or 'POST' in methods or 'PUT' in methods or 'DELETE' in methods or 'PATCH' in methods:
                print(f"{methods}: {route.path}")
    print("=========================\n")

def _mount_frontend(app: FastAPI, frontend_path: Path) -> None:
    """
    Monta los archivos estáticos del frontend (HTML, JS, CSS) en la raíz de la API.

    Permite servir la interfaz de usuario desde el mismo servidor que la API,
    comprobando previamente que el directorio especificado existe.

    Args:
        app (FastAPI): La instancia de la aplicación FastAPI.
        frontend_path (Path): La ruta al directorio que contiene los archivos
            estáticos del frontend.

    Returns:
        None
    """
    if frontend_path.exists():
        app.mount(
            "/", StaticFiles(directory=str(frontend_path), html=True), name="frontend"
        )
    else:
        print(f"[AVISO] No se encontro la carpeta del frontend en: {frontend_path}")


# Creamos la instancia por defecto para Uvicorn
app = create_app()