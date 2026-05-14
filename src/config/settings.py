"""
Gestión de configuración de SolbaBackups.

La configuración se carga en orden de precedencia:
  1. Variables de entorno (prefijo SOLBA_)
  2. Archivo config.yaml en el directorio de trabajo
  3. Valores por defecto
"""

from __future__ import annotations

import sys
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    _base_dir_path = os.path.dirname(sys.executable)
else:
    _base_dir_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

load_dotenv(os.path.join(_base_dir_path, '.env'))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rutas base
# ---------------------------------------------------------------------------
BASE_DIR = Path(_base_dir_path).resolve()
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"
DEFAULT_BACKUP_DIR = BASE_DIR / "backups"


# ---------------------------------------------------------------------------
# Esquema de configuración por defecto
# ---------------------------------------------------------------------------
_DEFAULTS: Dict[str, Any] = {
    "backup_dir": str(DEFAULT_BACKUP_DIR),
    "log_level": "INFO",
    "compression": "zip",  # zip | tar.gz | none
    "encryption": False,
    "encryption_key": "",
    "retention_days": 30,
    "google_drive": {
        "enabled": False,
        "credentials_file": "credentials.json",
        "token_file": "token.json",
        "folder_id": "",
    },
    "databases": [],  # lista de perfiles de BD
    "folders": [],  # lista de carpetas a respaldar
    "schedules": [],  # tareas programadas
    "sync": {
        "enabled": False,
        "pairs": [],  # [{source, destination}]
    },
}


class Settings:
    """Carga y expone la configuración de la aplicación."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config: Dict[str, Any] = dict(_DEFAULTS)
        path = config_path or DEFAULT_CONFIG_PATH
        if path.exists():
            self._load_yaml(path)
        self._apply_env_overrides()

    # ------------------------------------------------------------------
    # Carga
    # ------------------------------------------------------------------
    def _load_yaml(self, path: Path) -> None:
        """Lee el archivo YAML y sobreescribe los valores por defecto."""
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        self._deep_merge(self._config, data)
        logger.info("Configuración cargada desde %s", path)

    def _apply_env_overrides(self) -> None:
        """Sobreescribe valores con variables de entorno SOLBA_*."""
        mapping = {
            "SOLBA_BACKUP_DIR": ("backup_dir",),
            "SOLBA_LOG_LEVEL": ("log_level",),
            "SOLBA_COMPRESSION": ("compression",),
            "SOLBA_ENCRYPTION": ("encryption",),
            "SOLBA_RETENTION_DAYS": ("retention_days",),
            "SOLBA_GDRIVE_ENABLED": ("google_drive", "enabled"),
            "SOLBA_GDRIVE_FOLDER_ID": ("google_drive", "folder_id"),
        }
        for env_key, cfg_path in mapping.items():
            value = os.getenv(env_key)
            if value is not None:
                self._set_nested(self._config, cfg_path, value)

    # ------------------------------------------------------------------
    # Acceso
    # ------------------------------------------------------------------
    def get(self, *keys: str, default: Any = None) -> Any:
        """Obtiene un valor anidado: settings.get('google_drive', 'enabled')."""
        node = self._config
        for key in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(key, default)
        return node

    @property
    def backup_dir(self) -> Path:
        return Path(self._config["backup_dir"])

    @property
    def log_level(self) -> str:
        return self._config["log_level"]

    @property
    def compression(self) -> str:
        return self._config["compression"]

    @property
    def retention_days(self) -> int:
        return int(self._config["retention_days"])

    @property
    def databases(self) -> List[Dict[str, Any]]:
        return self._config.get("databases", [])

    @property
    def folders(self) -> List[Dict[str, Any]]:
        return self._config.get("folders", [])

    @property
    def schedules(self) -> List[Dict[str, Any]]:
        return self._config.get("schedules", [])

    @property
    def google_drive(self) -> Dict[str, Any]:
        return self._config.get("google_drive", {})

    @property
    def sync(self) -> Dict[str, Any]:
        return self._config.get("sync", {})

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------
    def save(self, path: Optional[Path] = None) -> None:
        """Persiste la configuración actual en YAML."""
        target = path or DEFAULT_CONFIG_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            yaml.dump(self._config, fh, allow_unicode=True, sort_keys=False)
        logger.info("Configuración guardada en %s", target)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                Settings._deep_merge(base[key], value)
            else:
                base[key] = value

    @staticmethod
    def _set_nested(d: Dict, keys: tuple, value: Any) -> None:
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value


# Instancia global (singleton ligero)
settings = Settings()
