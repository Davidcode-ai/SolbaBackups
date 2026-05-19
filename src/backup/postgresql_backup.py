"""PostgreSQL backup provider module."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from .base import BaseBackup


def _find_pg_dump_path() -> Optional[str]:
    """
    Busca la ruta de pg_dump en el sistema (PATH o rutas estándar de Windows).
    Si encuentra varias versiones, selecciona la más reciente.
    """
    # 1. Verificar si está en el PATH
    if shutil.which("pg_dump"):
        return "pg_dump"
    
    # 2. Buscar en Program Files
    search_paths = [
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "PostgreSQL",
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "PostgreSQL"
    ]
    
    candidates = []
    
    for base_path in search_paths:
        if base_path.exists() and base_path.is_dir():
            # Buscar en cada carpeta de versión
            for version_dir in base_path.iterdir():
                if version_dir.is_dir():
                    exe_path = version_dir / "bin" / "pg_dump.exe"
                    if exe_path.exists() and exe_path.is_file():
                        # Tratar de obtener la versión (ej. "15", "16")
                        try:
                            version = float(version_dir.name)
                        except ValueError:
                            version = 0.0
                        candidates.append((version, str(exe_path)))
                        
    if candidates:
        # Ordenar por versión descendente y devolver el mayor
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
        
    return None


class PostgreSQLBackup(BaseBackup):
    """Backup provider for PostgreSQL databases using pg_dump."""

    def _do_backup(self, timestamp: str, **kwargs: Any) -> Path:
        """Performs a backup of a PostgreSQL database using pg_dump.

        Args:
            timestamp: The current timestamp string to use in filenames.
            **kwargs: Must contain connection parameters
                (dbname, user, host, port, password).

        Returns:
            The path to the created backup file.

        Raises:
            ValueError: If required connection parameters are missing.
            RuntimeError: If pg_dump is not found.
            subprocess.CalledProcessError: If pg_dump fails.
        """
        dbname = kwargs.get("dbname")
        if not dbname:
            raise ValueError("dbname is required for PostgreSQL backup.")
            
        pg_dump_cmd = _find_pg_dump_path()
        if not pg_dump_cmd:
            raise RuntimeError("No se ha detectado PostgreSQL instalado en este equipo. Instálelo para poder realizar copias.")

        user = kwargs.get("user", "postgres")
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", "5432")
        password = kwargs.get("password", "")

        dest_filename = f"{dbname}_{timestamp}.sql"
        dest_path = self.dest_dir / dest_filename

        env = None
        if password:
            env = os.environ.copy()
            env["PGPASSWORD"] = password

        command = [
            pg_dump_cmd,
            "-h",
            str(host),
            "-p",
            str(port),
            "-U",
            str(user),
            "-f",
            str(dest_path),
            str(dbname),
        ]

        subprocess.run(command, env=env, check=True, capture_output=True)

        return dest_path
