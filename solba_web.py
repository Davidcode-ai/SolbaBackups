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
