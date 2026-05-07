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
    """
    crud.setting_set_many(db, settings_in.settings)
    updated_settings = crud.setting_get_all(db)
    return {"settings": updated_settings}
