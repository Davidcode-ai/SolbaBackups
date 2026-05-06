from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
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
