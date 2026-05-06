"""
src/connectors/postgresql.py — Conector para PostgreSQL.
"""

import asyncio
import logging
import os
from pathlib import Path

from src.connectors.base import BaseConnector
from src.db.models import Job

log = logging.getLogger(__name__)

class PostgreSQLConnector(BaseConnector):
    """
    Implementa la extracción de PostgreSQL usando pg_dump mediante subprocesos.
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
        # se debe desencriptar aquí. Para este MVP, asumimos que db_password_enc
        # tiene la contraseña en texto plano inyectada temporalmente.
        if getattr(job, "db_password_enc", None):
            env["PGPASSWORD"] = job.db_password_enc
            
        # Ejecutar subproceso
        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='replace').strip()
            raise Exception(f"pg_dump falló con código {process.returncode}:\n{error_msg}")
            
        return True
