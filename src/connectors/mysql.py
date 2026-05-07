"""
src/connectors/mysql.py — Conector para MySQL / MariaDB.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path

from src.connectors.base import BaseConnector
from src.db.models import Job

log = logging.getLogger(__name__)

class MySQLConnector(BaseConnector):
    """
    Implementa la extracción de MySQL usando mysqldump mediante subprocesos en threads.
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
        password = getattr(job, "db_password", None) or getattr(job, "db_password_enc", None)
        if password:
            env["MYSQL_PWD"] = password
            
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
                raise Exception(f"mysqldump falló con código {e.returncode}:\n{error_msg}")
        
        # Ejecutar en hilo separado para sortear las limitaciones del Event Loop en Windows
        try:
            await asyncio.to_thread(_run_dump)
        except FileNotFoundError:
            raise Exception(
                "El comando 'mysqldump' no se encuentra en el sistema. "
                "Asegúrate de que MySQL/MariaDB está instalado y añadido al PATH de Windows."
            )
            
        return True
