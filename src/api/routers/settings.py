"""
src/api/routers/settings.py — Endpoints para configuración global.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Any

from src.core import models
from src.db import crud
from src.db.database import get_db

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("", response_model=models.AppSettingsRead)
def get_settings(db: Session = Depends(get_db)):
    """
    Devuelve todas las variables de configuración global guardadas en la BD.
    """
    settings_dict = crud.setting_get_all(db)
    return {"settings": settings_dict}

@router.put("", response_model=models.AppSettingsRead)
def update_settings(settings_in: models.AppSettingsUpdate, db: Session = Depends(get_db)):
    """
    Actualiza o crea variables de configuración global.
    Acepta tanto JSON anidado en {"settings": {...}} como JSON plano {"key": "value"}.
    """
    # Extraemos todos los campos, incluyendo los "extra" del JSON plano
    data = settings_in.model_dump(exclude_unset=True)
    # Extraemos el dict 'settings' si viene
    settings_dict = data.pop("settings", {}) or {}
    # Juntamos todo
    settings_dict.update(data)

    crud.setting_set_many(db, settings_dict)
    updated_settings = crud.setting_get_all(db)
    return {"settings": updated_settings}
