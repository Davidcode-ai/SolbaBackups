"""
src/connectors/postgresql.py — Conector para PostgreSQL.
"""

import asyncio
import glob
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from src.connectors.base import BaseConnector
from src.db.models import Job

log = logging.getLogger(__name__)

# Tiempo máximo para pg_dump (2 h, alineado con el timeout del pipeline)
_DUMP_TIMEOUT_SEC = 7200

# Windows: 0xC000013A — proceso terminado al iniciar (DLL/PATH) o interrupción
_WIN_STATUS_CONTROL_C_EXIT = 3221225786


def _windows_subprocess_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def _find_pg_dump() -> str:
    """Resuelve pg_dump en PATH o en instalaciones típicas de PostgreSQL."""
    found = shutil.which("pg_dump")
    if found:
        return found

    if sys.platform == "win32":
        patterns = [
            r"C:\Program Files\PostgreSQL\*\bin\pg_dump.exe",
            r"C:\Program Files (x86)\PostgreSQL\*\bin\pg_dump.exe",
        ]
        candidates: list[str] = []
        for pattern in patterns:
            candidates.extend(glob.glob(pattern))
        if candidates:
            return sorted(candidates, reverse=True)[0]

    return "pg_dump"


def _ensure_pg_bin_in_path(env: dict[str, str], pg_dump_exe: str) -> None:
    """Añade el directorio bin de PostgreSQL al PATH del subproceso (DLLs)."""
    pg_bin = str(Path(pg_dump_exe).resolve().parent)
    current = env.get("PATH", "")
    if pg_bin.lower() not in current.lower():
        env["PATH"] = pg_bin + os.pathsep + current


def _get_job_db_password(job: Job) -> str | None:
    """Devuelve la contraseña en texto plano del job, si está definida."""
    raw = getattr(job, "db_password", None)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _build_pg_dump_env(job: Job, pg_dump_exe: str) -> dict[str, str]:
    """
    Copia el entorno del proceso e inyecta PGPASSWORD cuando el job tiene
    contraseña (nunca en la línea de comandos).
    """
    env = os.environ.copy()
    _ensure_pg_bin_in_path(env, pg_dump_exe)
    password = _get_job_db_password(job)
    if password is not None:
        env["PGPASSWORD"] = password
    return env


def _format_dump_error(
    returncode: int,
    stderr: str,
    stdout: str,
    cmd: list[str],
) -> str:
    parts = [
        f"pg_dump falló con código {returncode}",
        f"Comando: {' '.join(cmd)}",
    ]
    if stderr.strip():
        parts.append(f"stderr:\n{stderr.strip()}")
    if stdout.strip():
        parts.append(f"stdout:\n{stdout.strip()[:2000]}")
    if not stderr.strip() and not stdout.strip():
        parts.append("(sin salida en stderr/stdout)")

    if returncode in (_WIN_STATUS_CONTROL_C_EXIT, -1073741510):
        parts.append(
            "En Windows este código suele indicar que pg_dump.exe no pudo "
            "arrancar (faltan DLL de PostgreSQL en PATH). Instala el cliente "
            "PostgreSQL y añade su carpeta 'bin' al PATH del sistema."
        )
    elif returncode == 1 and "password" in stderr.lower():
        parts.append(
            "PostgreSQL exige contraseña: guarda db_password en el job para "
            "enviarla vía PGPASSWORD (el comando usa --no-password)."
        )

    return "\n".join(parts)


def _run_dump(
    job: Job,
    cmd: list[str],
    output_file_path: Path,
    pg_dump_exe: str,
) -> None:
    """
    Ejecuta pg_dump escribiendo la salida en output_file_path.

    Hereda os.environ y pasa la contraseña del job solo por PGPASSWORD.
    """
    env = _build_pg_dump_env(job, pg_dump_exe)
    stderr_data = b""
    dump_ok = False

    try:
        with open(output_file_path, "wb") as dump_file:
            proc = subprocess.Popen(
                cmd,
                env=env,
                stdout=dump_file,
                stderr=subprocess.PIPE,
                creationflags=_windows_subprocess_flags(),
            )
            try:
                stderr_data, _ = proc.communicate(timeout=_DUMP_TIMEOUT_SEC)
            except subprocess.TimeoutExpired:
                proc.kill()
                stderr_data, _ = proc.communicate()
                hours = _DUMP_TIMEOUT_SEC // 3600
                raise RuntimeError(
                    f"pg_dump excedió el tiempo límite de {hours} horas."
                ) from None

        if proc.returncode != 0:
            stderr_text = (stderr_data or b"").decode(
                "utf-8", errors="replace"
            )
            raise RuntimeError(
                _format_dump_error(proc.returncode, stderr_text, "", cmd)
            )

    except FileNotFoundError:
        raise FileNotFoundError(
            "El comando 'pg_dump' no se encuentra en el sistema. "
            "Instala PostgreSQL (cliente) y añade su carpeta 'bin' al PATH."
        ) from None
    except OSError as os_err:
        raise RuntimeError(
            f"No se pudo ejecutar pg_dump ({pg_dump_exe}): {os_err}"
        ) from os_err
    else:
        if not output_file_path.exists() or output_file_path.stat().st_size == 0:
            raise RuntimeError(
                "pg_dump terminó sin error aparente pero el archivo está vacío: "
                f"{output_file_path}"
            )

        dump_ok = True
        log.info(
            "Volcado PostgreSQL OK: %s (%d bytes)",
            output_file_path.name,
            output_file_path.stat().st_size,
        )
    finally:
        # Si falla el proceso, eliminamos el temporal para no dejar basura.
        if not dump_ok and output_file_path.exists():
            try:
                output_file_path.unlink()
                log.warning(
                    "Temporal de pg_dump eliminado tras fallo: %s",
                    output_file_path,
                )
            except OSError as cleanup_err:
                log.warning(
                    "No se pudo eliminar temporal de pg_dump '%s': %s",
                    output_file_path,
                    cleanup_err,
                )


class PostgreSQLConnector(BaseConnector):
    """
    Implementa la extracción de PostgreSQL usando pg_dump mediante subprocesos.
    """

    async def extract(self, job: Job, output_file_path: Path) -> bool:
        campos_faltantes = []
        if not job.db_name:
            campos_faltantes.append("Nombre de BD (db_name)")
        if not job.db_host:
            campos_faltantes.append("Host del servidor (db_host)")
        if not job.db_user:
            campos_faltantes.append("Usuario de la BD (db_user)")
        if campos_faltantes:
            raise ValueError(
                "Faltan datos críticos para ejecutar la extracción: "
                f"{', '.join(campos_faltantes)}. "
                "Por favor, edita el Job y completa la configuración."
            )

        pg_dump_exe = _find_pg_dump()
        log.info(
            "Iniciando volcado de PostgreSQL (BD: %s) con %s",
            job.db_name,
            pg_dump_exe,
        )

        cmd: list[str] = [pg_dump_exe]
        if job.db_host:
            cmd.extend(["-h", str(job.db_host)])
        if job.db_port:
            cmd.extend(["-p", str(job.db_port)])
        if job.db_user:
            cmd.extend(["-U", str(job.db_user)])

        cmd.extend(["-F", "p", "--no-password", str(job.db_name)])

        output_path = Path(output_file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(_run_dump, job, cmd, output_path, pg_dump_exe)
        return True
