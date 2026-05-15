"""
solba_web.py — Punto de entrada principal de la aplicación SolbaBackups.

Este script arranca el servidor web Uvicorn, inicializa el framework FastAPI
y configura el nivel global de logging para monitorizar las solicitudes HTTP
y la ejecución de las tareas en segundo plano.
"""
import sys
import os

# Parche para evitar crasheos de Uvicorn en modo noconsole por falta de isatty()
# Cuando la aplicación corre como Servicio de Windows (sin consola visible),
# sys.stdout y sys.stderr son None. Uvicorn intenta escribir en ellos o comprobar
# si son interactivos (isatty()), provocando excepciones fatales.
# Solución: Redirigir a os.devnull (el abismo) si son None.
# encoding='utf-8' evita UnicodeEncodeError con emojis/caracteres especiales en Windows (cp1252)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

# Forzar UTF-8 como codificación de E/S estándar de Python
# Esto garantiza que los logs y print() manejen correctamente caracteres especiales
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# Asegurar que el directorio del script (raíz del proyecto) esté en el sys.path
# Parche crucial para el empaquetado con PyInstaller (modo frozen)
if getattr(sys, 'frozen', False):
    # Ejecutándose como .exe empaquetado con PyInstaller
    # sys.executable apunta a la ubicación real del binario final.
    base_path = os.path.dirname(sys.executable)
else:
    # Ejecutándose como script Python normal
    # __file__ indica la ubicación del script .py.
    base_path = os.path.dirname(os.path.abspath(__file__))

# Agregamos la ruta resuelta (base_path) al inicio de sys.path (index 0).
# Esto asegura que las importaciones (ej. 'src.api...') resuelvan desde este directorio,
# incluso si el servicio/ejecutable es invocado desde otra carpeta de trabajo.
root_dir = base_path
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from dotenv import load_dotenv

# Construimos la ruta absoluta al archivo .env utilizando el base_path resuelto previamente.
# Esto asegura que el archivo .env se busque junto al ejecutable o script real,
# independientemente del directorio de trabajo actual (CWD) del Servicio de Windows.
env_path = os.path.join(base_path, '.env')
print(f"DEBUG: Buscando archivo .env en: {env_path}")
load_dotenv(env_path)

import logging

# Configurar logging global (stdout ya apunta a devnull UTF-8 en modo noconsole)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    force=True,
)


if __name__ == "__main__":
    import uvicorn
    print("Iniciando el servidor web de SolbaBackups...")
    print("El frontend estara disponible en: http://localhost:8765/")
    # Ejecuta la aplicación de FastAPI ubicada en src/api/server.py
    from src.api.server import app
    uvicorn.run(app, host="0.0.0.0", port=8765)
