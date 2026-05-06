import uvicorn

if __name__ == "__main__":
    print("Iniciando el servidor web de SolbaBackups...")
    print("El frontend estará disponible en: http://localhost:8765/")
    # Ejecuta la aplicación de FastAPI ubicada en src/api/server.py
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8765, reload=True)
