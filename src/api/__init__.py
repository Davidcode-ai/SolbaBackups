"""
src/api/__init__.py

Paquete de la capa API de SolbaBackups Web.

Expone la función de fábrica ``create_app`` como punto de entrada público
para que ``solba_web.py`` y los tests puedan instanciar la aplicación
FastAPI sin importar directamente ``server.py``.
"""

from src.api.server import create_app

__all__ = ["create_app"]
