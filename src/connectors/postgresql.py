"""
src/connectors/postgresql.py — Conector para PostgreSQL.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path

from src.connectors.base import BaseConnector
from src.db.models import Job

log = logging.getLogger(__name__)

class PostgreSQLConnector(BaseConnector):
    """
    Implementa la extracción de PostgreSQL usando pg_dump mediante subprocesos en threads.
    """
    
    async def extract(self, job: Job, output_file_path: Path) -> bool:
        log.info(f"Iniciando volcado de PostgreSQL (BD: {job.db_name})")
        
        # El comando base
        cmd = ["pg_dump"]
        
        if job.db_host:
            cmd.extend(["-h", job.db_host])
        if job.db_port:
            cmd.extend(["-p", str(job.db_port)])
        if job.db_user:
            cmd.extend(["-U", job.db_user])
            
        # Parámetros adicionales: 
        # -c (clean)
        # -O (no owner)
        # -f (output file)
        cmd.extend(["-c", "-O", "-f", str(output_file_path), job.db_name])
        
        # Configurar variables de entorno (seguridad: no pasar password como flag)
        env = os.environ.copy()
        
        # TODO: En la implementación final, si la password está encriptada (Fernet),
        # se debe desencriptar aquí. Para este MVP, verificamos ambas columnas.
        password = getattr(job, "db_password", None) or getattr(job, "db_password_enc", None)
        if password:
            env["PGPASSWORD"] = password
            
        def _run_dump():
            try:
                subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True
                )
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.strip() if e.stderr else str(e)
                raise Exception(f"pg_dump falló con código {e.returncode}:\n{error_msg}")
        
        # Ejecutar en hilo separado para sortear las limitaciones del Event Loop en Windows
        try:
            await asyncio.to_thread(_run_dump)
        except FileNotFoundError:
            raise Exception(
                "El comando 'pg_dump' no se encuentra en el sistema. "
                "Asegúrate de que PostgreSQL está instalado y añadido al PATH de Windows."
            )
            
        return True
