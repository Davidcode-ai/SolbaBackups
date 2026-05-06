"""
src/api/server.py — Fábrica de la Aplicación FastAPI.

Este módulo define la función ``create_app`` que construye y configura
la instancia principal de FastAPI. Sigue el patrón Application Factory
para facilitar los tests (cada test puede crear su propia instancia limpia).

Responsabilidades:
    - Registrar todos los routers de la API bajo el prefijo ``/api/v1``.
    - Montar los archivos estáticos del frontend en la ruta raíz ``/``.
    - Configurar middleware de CORS para peticiones desde localhost.
    - Definir los eventos de ciclo de vida (startup / shutdown):
        * Startup:  Crear tablas en BD, iniciar APScheduler, cargar jobs activos.
        * Shutdown: Detener el scheduler, cerrar conexiones de BD.
    - Añadir un handler 404 que redirige al ``index.html`` del SPA para
      soportar la navegación del lado del cliente (client-side routing).
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
    pass


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
