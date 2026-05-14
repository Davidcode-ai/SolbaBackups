import pytest
from src.db import crud

def test_api_jobs_crud(client, db_session):
    """Prueba el ciclo de vida completo de un Job a través de la API."""
    # 1. Crear Job (POST /api/v1/jobs/)
    new_job = {
        "name": "API Test Job",
        "db_type": "mysql",
        "db_host": "localhost",
        "db_name": "test_db",
        "db_user": "root",
        "db_password": "password123",
        "schedule": {
            "schedule_type": "manual"
        }
    }
    response = client.post("/api/v1/jobs", json=new_job)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API Test Job"
    assert "id" in data
    job_id = data["id"]
    
    # 2. Obtener Job (GET /api/v1/jobs/{job_id})
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["name"] == "API Test Job"
    
    # 3. Actualizar Job (PUT /api/v1/jobs/{job_id})
    update_data = {
        "name": "API Test Job Updated",
        "db_type": "mysql",
    }
    response = client.put(f"/api/v1/jobs/{job_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["name"] == "API Test Job Updated"
    
    # 4. Eliminar Job (DELETE /api/v1/jobs/{job_id})
    response = client.delete(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 204
    
    # 5. Verificar que ya no existe
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 404

def test_api_history(client, db_session):
    """Prueba los endpoints de historial de ejecuciones."""
    # Crear job y un historial manualmente para probar la API
    job = crud.job_create(db_session, {"name": "History Job", "db_type": "folder"})
    run = crud.run_create(db_session, job_id=job.id, job_name=job.name, trigger="manual")
    crud.run_finish(db_session, run.id, status="success")
    
    # 1. GET /api/v1/history (Global)
    response = client.get("/api/v1/history")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    
    # 2. GET /api/v1/history/{job_id} (Por Job)
    response = client.get(f"/api/v1/history/job/{job.id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == run.id
    assert data[0]["status"] == "success"

def test_api_settings_update(client):
    """Prueba la actualización masiva de configuraciones."""
    settings_data = {
        "notification_email": "newadmin@test.com",
        "notify_errors_only": True
    }
    response = client.put("/api/v1/settings", json=settings_data)
    assert response.status_code == 200
    
    # Validar que se guardó
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["notification_email"] == "newadmin@test.com"
    assert data["settings"]["notify_errors_only"] is True

def test_api_utils_test_connection_folder(client):
    """Prueba el endpoint de test_connection para carpetas locales."""
    # Enviar una ruta actual como prueba
    payload = {
        "db_type": "folder",
        "db_name": "."  # Directorio actual siempre debe existir
    }
    response = client.post("/api/v1/jobs/test-connection", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "accesible" in data["message"].lower()

def test_api_auth_google_status(client):
    """Prueba el endpoint de status de Google."""
    response = client.get("/api/v1/auth/google/status")
    assert response.status_code == 200
