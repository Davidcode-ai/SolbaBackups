"""
solba_web.py — Punto de entrada principal de la aplicación SolbaBackups.

Este script arranca el servidor web Uvicorn, inicializa el framework FastAPI
y configura el nivel global de logging para monitorizar las solicitudes HTTP
y la ejecución de las tareas en segundo plano.
"""
import sys
import os

# Asegurar que el directorio del script (raíz del proyecto) esté en el sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import uvicorn
import logging

if __name__ == "__main__":
    # Configurar el logging a nivel global para ver qué hace APScheduler y el backend
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )

    print("Iniciando el servidor web de SolbaBackups...")
    print("El frontend estará disponible en: http://localhost:8765/")
    # Ejecuta la aplicación de FastAPI ubicada en src/api/server.py
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8765, reload=False)
