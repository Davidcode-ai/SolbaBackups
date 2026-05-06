"""
src/connectors/mysql.py — Conector para MySQL / MariaDB.
"""

import asyncio
import logging
import os
from pathlib import Path

from src.connectors.base import BaseConnector
from src.db.models import Job

log = logging.getLogger(__name__)

class MySQLConnector(BaseConnector):
    """
    Implementa la extracción de MySQL usando mysqldump mediante subprocesos.
    """
    
    async def extract(self, job: Job, output_file_path: Path) -> bool:
        log.info(f"Iniciando volcado de MySQL (BD: {job.db_name})")
        
        # El comando base
        cmd = ["mysqldump"]
        
        if job.db_host:
            cmd.extend(["-h", job.db_host])
        if job.db_port:
            cmd.extend(["-P", str(job.db_port)])
        if job.db_user:
            cmd.extend(["-u", job.db_user])
            
        # Parámetros adicionales
        cmd.extend(["--opt", f"--result-file={output_file_path}", job.db_name])
        
        # Configurar variables de entorno para la password de MySQL
        env = os.environ.copy()
        if getattr(job, "db_password_enc", None):
            env["MYSQL_PWD"] = job.db_password_enc
            
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
            raise Exception(f"mysqldump falló con código {process.returncode}:\n{error_msg}")
            
        return True
