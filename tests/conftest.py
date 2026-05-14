import os
import pytest
from fastapi.testclient import TestClient

# Configurar BD local para tests antes de importar la app
os.environ["SOLBA_DB_PATH"] = "test_solba_data.sqlite3"

from src.api.server import app
from src.db.database import Base, engine, SessionLocal

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Crea las tablas una vez por sesión de prueba."""
    Base.metadata.create_all(bind=engine)
    yield
    # Limpieza final
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test_solba_data.sqlite3"):
        try:
            os.remove("test_solba_data.sqlite3")
        except:
            pass

@pytest.fixture
def db_session():
    """Provee una sesión limpia de base de datos para cada test."""
    db = SessionLocal()
    # Limpiar tablas clave antes de cada test para aislar
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client():
    """Provee un cliente de pruebas para FastAPI."""
    with TestClient(app) as c:
        yield c
