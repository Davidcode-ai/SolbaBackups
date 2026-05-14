"""
solba_web.py — Punto de entrada principal de la aplicación SolbaBackups.

Este script arranca el servidor web Uvicorn, inicializa el framework FastAPI
y configura el nivel global de logging para monitorizar las solicitudes HTTP
y la ejecución de las tareas en segundo plano.
"""
import sys
import os

# Parche para evitar crasheos de Uvicorn en modo noconsole por falta de isatty()
# encoding='utf-8' evita UnicodeEncodeError con emojis/caracteres especiales en Windows (cp1252)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

# Forzar UTF-8 como codificación de E/S estándar de Python
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# Asegurar que el directorio del script (raíz del proyecto) esté en el sys.path
if getattr(sys, 'frozen', False):
    # Ejecutándose como .exe empaquetado con PyInstaller
    base_path = os.path.dirname(sys.executable)
else:
    # Ejecutándose como script Python normal
    base_path = os.path.dirname(os.path.abspath(__file__))

root_dir = base_path
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from dotenv import load_dotenv

env_path = os.path.join(base_path, '.env')
print(f"DEBUG: Buscando archivo .env en: {env_path}")
load_dotenv(env_path)

# Configurar logging con UTF-8 a nivel de módulo (necesario cuando se importa como servicio,
# no solo cuando se ejecuta como __main__)
import logging

_log_handler = logging.StreamHandler(stream=sys.stdout)
_log_handler.setLevel(logging.INFO)
_log_handler.stream = open(
    os.path.join(base_path, 'solba_service.log'), 'a', encoding='utf-8', buffering=1
) if getattr(sys, 'frozen', False) else sys.stdout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[_log_handler],
    force=True,   # Reemplaza cualquier config previa
)


if __name__ == "__main__":
    import uvicorn
    print("Iniciando el servidor web de SolbaBackups...")
    print("El frontend estara disponible en: http://localhost:8765/")
    # Ejecuta la aplicación de FastAPI ubicada en src/api/server.py
    from src.api.server import app
    uvicorn.run(app, host="0.0.0.0", port=8765)
