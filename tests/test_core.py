import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

# Importar dependencias de la app
from src.api.server import app
from src.db.database import Base, engine
from src.db.database import SessionLocal
from src.db import crud
from src.core.models import JobCreate, JobUpdate
from src.destinations.local import LocalDestination
from src.core.job_manager import JobManager


def test_api_endpoints_200_ok(client):
    """Prueba 1: Endpoints de la API GET jobs y settings devuelven 200 OK."""
    response_jobs = client.get("/api/v1/jobs")
    assert response_jobs.status_code == 200
    assert isinstance(response_jobs.json(), list)

    response_settings = client.get("/api/v1/settings")
    assert response_settings.status_code == 200
    assert "settings" in response_settings.json()


def test_schema_validation_empty_password(client, db_session):
    """Prueba 2: Validación de Schemas: Contraseña vacía no sobrescribe la existente."""
    # 1. Crear un job directamente en la BD (o vía API) con una contraseña
    job_data = {
        "name": "Test Job Pass",
        "db_type": "postgresql",
        "db_password": "supersecret"
    }
    job = crud.job_create(db_session, job_data)
    
    # 2. Hacer PUT enviando contraseña vacía (simulando frontend)
    update_data = {
        "name": "Test Job Pass",
        "db_type": "postgresql",
        "db_password": ""
    }
    response = client.put(f"/api/v1/jobs/{job.id}", json=update_data)
    assert response.status_code == 200
    
    # 3. Verificar que la contraseña no se borró en la base de datos
    updated_job = crud.job_get_by_id(db_session, job.id)
    assert updated_job.db_password == "supersecret"


@pytest.mark.asyncio
async def test_local_destination_route_creation(tmp_path):
    """Prueba 3: Cálculo de Rutas: Rutas de destino local se crean si no existen."""
    dest = LocalDestination()
    
    # Definir una ruta anidada que NO existe
    target_dir = tmp_path / "new_folder" / "subfolder"
    assert not target_dir.exists()
    
    # Crear un archivo dummy de origen
    source_file = tmp_path / "backup.zip"
    source_file.write_text("contenido dummy")
    
    # Ejecutar la subida (esto debe crear la ruta de destino automáticamente)
    await dest.upload(source_file, str(target_dir))
    
    # Verificar que la ruta se creó y el archivo fue movido allí
    assert target_dir.exists()
    assert (target_dir / "backup.zip").exists()


@pytest.mark.asyncio
async def test_notification_filter_only_errors(db_session, tmp_path):
    """Prueba 4: Filtro de Notificaciones: 'Solo errores' no manda email si el backup es exitoso."""
    # 1. Configurar los settings en la base de datos
    crud.setting_set(db_session, "notification_email", "admin@test.com")
    crud.setting_set(db_session, "notify_errors_only", "true")
    
    # 2. Crear un job dummy
    job = crud.job_create(db_session, {
        "name": "Test Job Notification",
        "db_type": "folder",
        "db_name": str(tmp_path) # Usar tmp_path como origen válido
    })
    
    manager = JobManager()
    
    # 3. Mockear send_email_notification para verificar que NO se llama
    #    y mockear la subida/compresión para que el backup sea exitoso rápidamente.
    with patch("src.core.notifications.send_email_notification") as mock_send_email:
        # Hacemos que la función upload de LocalDestination no haga nada
        with patch("src.destinations.local.LocalDestination.upload", return_value=True):
            # Simulamos el empaquetado para que no falle
            with patch("shutil.make_archive", return_value=str(tmp_path / "dummy.zip")):
                # Creamos el archivo dummy para que no falle el unlink
                (tmp_path / "dummy.zip").write_text("test")
                
                # Ejecutamos el job
                await manager.run_job(job.id, trigger="manual")
                
        # 4. Verificamos que el email NO fue enviado porque fue exitoso
        mock_send_email.assert_not_called()
        
        # Validar que sí se envía si falla
        # Simulamos un error
        with patch("shutil.make_archive", side_effect=Exception("Error forzado")):
            await manager.run_job(job.id, trigger="manual")
            
        # El email debe haber sido enviado una vez por el error
        mock_send_email.assert_called_once()
        args, kwargs = mock_send_email.call_args
        assert kwargs["to_email"] == "admin@test.com"
        assert "❌ Error en Backup" in kwargs["subject"]
