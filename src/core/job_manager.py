"""
src/core/job_manager.py — Orquestador del Pipeline de Backup.

Contiene la lógica central del JobManager que une la base de datos,
los conectores, compresores y destinos.
"""

import asyncio
import logging
import filecmp
import os
import re
import shutil
import subprocess
import tempfile
import traceback
import zipfile
from pathlib import Path

from src.db import crud
from src.db.database import SessionLocal
from src.processors.compressor import Compressor
from src.core.history_manager import HistoryManager

log = logging.getLogger(__name__)


def _safe_staging_cleanup(paths: list[Path], dest_local_path: str | None) -> None:
    """Elimina rutas temporales solo bajo el directorio temp del sistema."""
    if not paths:
        return

    temp_root = Path(tempfile.gettempdir()).resolve()
    dest_resolved = None
    if dest_local_path:
        try:
            dest_resolved = Path(dest_local_path).resolve()
        except (OSError, ValueError):
            dest_resolved = None

    seen: set[str] = set()
    for raw_path in paths:
        try:
            resolved = Path(raw_path).resolve()
        except (OSError, ValueError):
            continue

        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)

        if not str(resolved).startswith(str(temp_root)):
            log.warning("Omitiendo limpieza fuera de directorio temporal: %s", resolved)
            continue

        if dest_resolved:
            if resolved == dest_resolved:
                log.warning("Omitiendo limpieza del destino local: %s", resolved)
                continue
            try:
                resolved.relative_to(dest_resolved)
                log.warning("Omitiendo limpieza dentro del destino local: %s", resolved)
                continue
            except ValueError:
                pass

        if not resolved.exists():
            continue

        try:
            if resolved.is_dir():
                shutil.rmtree(resolved, ignore_errors=True)
            else:
                resolved.unlink(missing_ok=True)
        except Exception as exc:
            log.warning("No se pudo limpiar temporal %s: %s", resolved, exc)


class JobManager:
    """Orchestrate backup, folder packaging, true-sync mirror, and notifications.

    Used by the REST API and Windows scheduling flows. Non-sync jobs follow
    the dump or folder pipeline; ``db_type``/``engine`` ``sync`` routes to
    :meth:`_execute_pure_sync`.
    """

    def __init__(self):
        """Create a manager with the default ZIP :class:`~src.processors.compressor.Compressor`."""
        self.compressor = Compressor()

    def restore_backup(self, run_id: int) -> dict:
        """Restore database or folder artifacts produced by a **successful** run.

        Resolves ``backup_file_path`` (local path or Google Drive share URL),
        extracts archives when needed, infers the payload (``.sql``, ``.db``,
        tree), and runs engine-specific restore. All steps append rows via
        :class:`~src.core.history_manager.HistoryManager` on the same ``run_id``.

        Args:
            run_id: Primary key of the ``RunHistory`` row whose artifact must
                be restored.

        Returns:
            A dict with keys ``success`` (bool), ``run_id``, ``db_type``, and
            ``message`` on success.

        Raises:
            ValueError: Missing run/job, run not in ``success`` state, empty
                path, invalid Drive URL, or invalid target configuration.
            FileNotFoundError: Backup or extracted artifact not on disk.
            NotImplementedError: No restore path for the job's ``db_type``.
            RuntimeError: Subprocess or filesystem failure during restore (e.g.
                DB client errors, copy failures).

        Note:
            Temporary directories created for Drive downloads or ZIP extraction
            are removed in ``finally`` blocks where applicable.
        """
        history_manager = HistoryManager()

        with SessionLocal() as db:
            run = crud.run_get_by_id(db, run_id)
            if not run:
                raise ValueError(f"Run {run_id} no encontrado.")
            if (run.status or "").lower() != "success":
                raise ValueError(
                    f"Solo se puede restaurar un run en estado SUCCESS. Estado actual: {run.status}"
                )

            job = crud.job_get_by_id(db, run.job_id)
            if not job:
                raise ValueError(f"No se encontró el Job asociado al run {run_id}.")

            db_type = str(job.db_type or "").lower()

            backup_file_path = run.backup_file_path or ""
            print(f"DEBUG RESTORE: backup_file_path del run={run_id}: '{backup_file_path}'")
            
            # Inicializar variables para cleanup
            temp_dir_to_cleanup = None
            is_cloud_backup = False
            
            # Detectar si es un backup en Google Drive (URL) o local (ruta de archivo)
            if backup_file_path.startswith("https://drive.google.com"):
                # Es un backup en Google Drive - necesitamos descargarlo
                print(f"DEBUG RESTORE: Detectado backup en Google Drive")
                from src.destinations.google_drive import GoogleDriveDestination
                
                gdrive = GoogleDriveDestination()
                
                # Verificar que existe el archivo de credenciales
                credentials_file = os.path.join(os.getcwd(), "credentials.json")
                if not os.path.exists(credentials_file):
                    raise ValueError(
                        "No se encontró credentials.json para acceder a Google Drive."
                    )
                
                # Extraer file_id de la URL
                # URL format: https://drive.google.com/file/d/{file_id}/view?...
                file_id = backup_file_path.split("/d/")[1].split("/")[0] if "/d/" in backup_file_path else None
                if not file_id:
                    raise ValueError(f"No se pudo extraer el file_id de la URL de Google Drive: {backup_file_path}")
                
                print(f"DEBUG RESTORE: file_id extraído: {file_id}")
                
                # Crear directorio temporal para descargar
                temp_dir_to_cleanup = tempfile.mkdtemp(prefix="solba_restore_")
                backup_path = Path(temp_dir_to_cleanup) / f"backup_{run_id}.zip"
                
                # Descargar el archivo desde Google Drive
                import asyncio
                print(f"DEBUG RESTORE: Descargando archivo desde Google Drive a: {backup_path}")
                asyncio.run(gdrive.download_file(file_id, str(backup_path)))
                
                if not backup_path.exists():
                    raise FileNotFoundError(f"No se pudo descargar el archivo desde Google Drive")
                
                print(f"DEBUG RESTORE: Archivo descargado exitosamente")
                is_cloud_backup = True
                temp_dir_to_cleanup = str(backup_path.parent)
            else:
                # Es un backup local (ruta de archivo o carpeta)
                backup_path = Path(backup_file_path).expanduser()
                if not backup_path.is_absolute():
                    backup_path = Path.cwd() / backup_path
                backup_path = backup_path.resolve()
                print(f"DEBUG RESTORE: backup_path como Path: {backup_path}")
                print(f"DEBUG RESTORE: backup_path.exists(): {backup_path.exists()}")
                if not str(backup_path).strip():
                    raise ValueError(
                        "El run no contiene la ruta del backup (backup_file_path vacío)."
                    )
                if not backup_path.exists():
                    raise FileNotFoundError(
                        f"No se encontró el archivo de backup en disco: {backup_path}"
                    )

            history_manager.add_log(
                db,
                run_id,
                "INFO",
                f"Iniciando restauración desde backup: {backup_path}",
                stage="restore_init",
            )

            try:
                tmp_cleanup: tempfile.TemporaryDirectory | None = None
                tmp_dir_path: Path

                if backup_path.is_dir():
                    tmp_dir_path = backup_path
                    history_manager.add_log(
                        db,
                        run_id,
                        "INFO",
                        "Usando carpeta de backup en disco (contenido listo para restaurar).",
                        stage="restore_extract",
                    )
                elif zipfile.is_zipfile(backup_path):
                    history_manager.add_log(
                        db,
                        run_id,
                        "INFO",
                        "Descomprimiendo backup ZIP en carpeta temporal...",
                        stage="restore_extract",
                    )
                    tmp_cleanup = tempfile.TemporaryDirectory(prefix="solba_restore_")
                    tmp_dir_path = Path(tmp_cleanup.name)
                    with zipfile.ZipFile(backup_path, "r") as zf:
                        zf.extractall(tmp_dir_path)
                else:
                    history_manager.add_log(
                        db,
                        run_id,
                        "INFO",
                        "Preparando archivo de backup suelto (.sql / fichero)...",
                        stage="restore_extract",
                    )
                    tmp_cleanup = tempfile.TemporaryDirectory(prefix="solba_restore_")
                    tmp_dir_path = Path(tmp_cleanup.name)
                    shutil.copy2(backup_path, tmp_dir_path / backup_path.name)

                try:

                    extracted_path: Path | None = None

                    if db_type in ["postgresql", "mysql"]:
                        sql_candidates = sorted(tmp_dir_path.rglob("*.sql"))
                        if sql_candidates:
                            extracted_path = sql_candidates[0]
                        else:
                            extracted_files = [
                                p for p in tmp_dir_path.rglob("*") if p.is_file()
                            ]
                            if len(extracted_files) == 1:
                                extracted_path = extracted_files[0]
                    elif db_type in ("sqlite", "mdb"):
                        for pattern in (
                            "*.db",
                            "*.sqlite",
                            "*.sqlite3",
                            "*.mdb",
                            "*.accdb",
                        ):
                            db_candidates = sorted(tmp_dir_path.rglob(pattern))
                            if db_candidates:
                                extracted_path = db_candidates[0]
                                break
                    elif db_type in ("folder", "sync"):
                        extracted_path = tmp_dir_path
                        top_level = [
                            p
                            for p in tmp_dir_path.iterdir()
                            if p.name not in ("__MACOSX",)
                        ]
                        if len(top_level) == 1 and top_level[0].is_dir():
                            extracted_path = top_level[0]
                        else:
                            zip_candidates = sorted(
                                [
                                    p
                                    for p in tmp_dir_path.rglob("*.zip")
                                    if p.is_file()
                                ]
                            )
                            if len(zip_candidates) == 1:
                                inner_zip = zip_candidates[0]
                                inner_extract_dir = tmp_dir_path / "_folder_restore"
                                inner_extract_dir.mkdir(parents=True, exist_ok=True)
                                with zipfile.ZipFile(inner_zip, "r") as zf:
                                    zf.extractall(inner_extract_dir)
                                inner_top = [
                                    p
                                    for p in inner_extract_dir.iterdir()
                                    if p.name not in ("__MACOSX",)
                                ]
                                if len(inner_top) == 1 and inner_top[0].is_dir():
                                    extracted_path = inner_top[0]
                                else:
                                    extracted_path = inner_extract_dir

                    if not extracted_path or not extracted_path.exists():
                        raise FileNotFoundError(
                            f"No se pudo localizar archivo/carpeta restaurable para db_type='{db_type}'."
                        )

                    history_manager.add_log(
                        db,
                        run_id,
                        "INFO",
                        f"Archivo listo para restauración: {extracted_path.name if extracted_path.is_file() else extracted_path}",
                        stage="restore_extract",
                    )

                    history_manager.add_log(
                        db,
                        run_id,
                        "INFO",
                        f"Ejecutando restauración para motor: {db_type}",
                        stage="restore_execute",
                    )

                    if db_type == "postgresql":
                        if not job.db_host or not job.db_name or not job.db_user:
                            raise ValueError(
                                "Faltan datos de conexión PostgreSQL (host, db_name o db_user)."
                            )

                        cmd = [
                            "psql",
                            "-h",
                            str(job.db_host),
                            "-p",
                            str(job.db_port or 5432),
                            "-U",
                            str(job.db_user),
                            "-d",
                            str(job.db_name),
                            "-f",
                            str(extracted_path),
                        ]
                        env = os.environ.copy()
                        if job.db_password:
                            env["PGPASSWORD"] = str(job.db_password)

                        result = subprocess.run(
                            cmd, capture_output=True, text=True, env=env
                        )
                        if result.returncode != 0:
                            raise RuntimeError(
                                f"Restauración PostgreSQL falló (code={result.returncode}): "
                                f"{(result.stderr or result.stdout).strip()}"
                            )

                    elif db_type == "mysql":
                        if not job.db_host or not job.db_name or not job.db_user:
                            raise ValueError(
                                "Faltan datos de conexión MySQL (host, db_name o db_user)."
                            )

                        cmd = [
                            "mysql",
                            "-h",
                            str(job.db_host),
                            "-P",
                            str(job.db_port or 3306),
                            "-u",
                            str(job.db_user),
                        ]
                        if job.db_password:
                            cmd.append(f"--password={job.db_password}")
                        cmd.append(str(job.db_name))

                        with extracted_path.open(
                            "r", encoding="utf-8", errors="ignore"
                        ) as sql_fp:
                            result = subprocess.run(
                                cmd,
                                stdin=sql_fp,
                                capture_output=True,
                                text=True,
                            )
                        if result.returncode != 0:
                            raise RuntimeError(
                                f"Restauración MySQL falló (code={result.returncode}): "
                                f"{(result.stderr or result.stdout).strip()}"
                            )

                    elif db_type in ("sqlite", "mdb"):
                        if not job.db_name:
                            raise ValueError(
                                "Falta la ruta del archivo de base de datos de origen (db_name)."
                            )

                        original_db_path = Path(job.db_name)
                        if not original_db_path.exists():
                            raise FileNotFoundError(
                                f"El archivo de base de datos original no existe: {original_db_path}"
                            )

                        history_manager.add_log(
                            db,
                            run_id,
                            "INFO",
                            f"Sobrescribiendo archivo local: {original_db_path}",
                            stage="restore_execute",
                        )

                        try:
                            shutil.copy2(extracted_path, original_db_path)
                            history_manager.add_log(
                                db,
                                run_id,
                                "INFO",
                                "Archivo de base de datos restaurado correctamente.",
                                stage="restore_execute",
                            )
                        except OSError as os_err:
                            raise RuntimeError(
                                f"No se pudo sobrescribir el archivo de destino: {os_err}"
                            ) from os_err

                    elif db_type in ("folder", "sync"):
                        if not job.db_name:
                            raise ValueError(
                                "Falta la ruta de la carpeta de origen (db_name)."
                            )

                        original_folder_path = Path(job.db_name)
                        if not original_folder_path.exists() or not original_folder_path.is_dir():
                            raise FileNotFoundError(
                                f"La carpeta de origen no existe o no es un directorio: {original_folder_path}"
                            )

                        history_manager.add_log(
                            db,
                            run_id,
                            "INFO",
                            f"Volcando backup sobre carpeta de origen: {original_folder_path}",
                            stage="restore_execute",
                        )

                        try:
                            if not extracted_path or not Path(extracted_path).is_dir():
                                raise FileNotFoundError(
                                    "No hay una carpeta válida dentro del backup para restaurar."
                                )
                            shutil.copytree(
                                extracted_path,
                                original_folder_path,
                                dirs_exist_ok=True,
                            )
                            history_manager.add_log(
                                db,
                                run_id,
                                "INFO",
                                "Carpeta restaurada correctamente.",
                                stage="restore_execute",
                            )
                        except OSError as os_err:
                            raise RuntimeError(
                                f"Error al restaurar carpeta (permisos o disco): {os_err}"
                            ) from os_err

                    else:
                        raise NotImplementedError(
                            f"Restauración no implementada para db_type='{db_type}'."
                        )

                    history_manager.add_log(
                        db,
                        run_id,
                        "INFO",
                        "Restauración completada correctamente.",
                        stage="restore_done",
                    )

                    return {
                        "success": True,
                        "run_id": run_id,
                        "db_type": db_type,
                        "message": "Restauración ejecutada correctamente.",
                    }
                finally:
                    if tmp_cleanup is not None:
                        tmp_cleanup.cleanup()
            except Exception as exc:
                history_manager.add_log(
                    db,
                    run_id,
                    "ERROR",
                    f"Error durante restauración: {str(exc)}",
                    stage="restore_error",
                )
                raise
            finally:
                # Limpiar directorio temporal si fue un backup de Google Drive
                if temp_dir_to_cleanup:
                    try:
                        shutil.rmtree(temp_dir_to_cleanup, ignore_errors=True)
                        print(f"DEBUG RESTORE: Directorio temporal limpiado: {temp_dir_to_cleanup}")
                    except Exception as cleanup_err:
                        print(f"DEBUG RESTORE: Error limpiando directorio temporal: {cleanup_err}")

    async def _execute_pure_sync(self, job, run, db) -> tuple[int, str]:
        """Mirror ``job.source_local_path`` onto a local destination (true sync).

        Clears the **root** of the destination directory (not the parent), then
        copies every file and subdirectory from the source. If the destination
        folder's name matches the job name (several normalizations), the parent
        is used as the real destination to avoid nesting under a job-named leaf.

        Args:
            job: ORM row with ``source_local_path``, ``dest_local_path``,
                ``dest_type``, ``compress``, ``name``, and related fields.
            run: ORM run row (for log correlation).
            db: Open SQLAlchemy session.

        Returns:
            ``(total_bytes, destination_path_str)`` — sum of file sizes under the
            destination tree and its resolved path as a string.

        Raises:
            ValueError: Mirror requires local destination, compression must be
                off, missing paths, disallowed dest type, or source equals dest.
            NotADirectoryError: ``source_local_path`` is not a directory.
        """
        history_manager = HistoryManager()
        if not job.dest_local_path:
            raise ValueError(
                "La sincronización (espejo) requiere una carpeta de destino local."
            )
        if str(job.dest_type or "local").lower() != "local":
            raise ValueError(
                "La sincronización (espejo) solo está disponible con destino 'Carpeta local'."
            )
        if getattr(job, "compress", True):
            raise ValueError(
                "La sincronización no admite compresión ZIP; desactiva comprimir en la tarea."
            )
        if not job.source_local_path:
            raise ValueError("Origen local vacío (source_local_path / db_name).")

        src = Path(job.source_local_path).resolve()
        dest = Path(job.dest_local_path).resolve()

        name_variants = [
            job.name.lower(),
            job.name.replace(" ", "_").lower(),
            job.name.replace("_", " ").lower(),
        ]
        if dest.name.lower() in name_variants:
            dest = dest.parent

        if not src.is_dir():
            raise NotADirectoryError(f"El origen no es un directorio: {src}")
        if src == dest:
            raise ValueError("Origen y destino no pueden ser la misma ruta.")

        history_manager.add_log(
            db,
            run.id,
            "INFO",
            f"Sync puro: vaciar raíz de destino y copiar contenido de {src} en {dest}",
            stage="dump",
        )

        def _pure_sync_work() -> int:
            dest.mkdir(parents=True, exist_ok=True)
            for item in dest.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            for item in src.iterdir():
                if item.is_dir():
                    shutil.copytree(item, dest / item.name)
                else:
                    shutil.copy2(item, dest / item.name)
            return sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())

        total_bytes = await asyncio.to_thread(_pure_sync_work)
        history_manager.add_log(
            db,
            run.id,
            "INFO",
            f"Sync puro completado: {total_bytes} bytes reflejados en destino.",
            stage="done",
        )
        return total_bytes, str(dest)

    async def run_job(self, job_id: int, trigger: str = "manual") -> None:
        """Run the full backup pipeline for ``job_id`` inside a DB session.

        Creates a ``RUNNING`` history row, executes sync or standard pipeline
        under a two-hour timeout, applies retention side-effects, and sends
        configured email/WhatsApp notifications. Failures are recorded as
        ``failed`` runs; this method **does not re-raise** pipeline exceptions.

        Args:
            job_id: Database id of the job to execute.
            trigger: Origin label (e.g. ``\"manual\"``, ``\"scheduled\"``).

        Returns:
            ``None`` always; inspect ``RunHistory`` for outcome.

        Note:
            Staging paths are cleaned with :func:`_safe_staging_cleanup` so only
            system temp (and never the user's destination folder) is removed.
        """
        history_manager = HistoryManager()

        with SessionLocal() as db:
            # 1. Leer Job desde la base de datos
            job = crud.job_get_by_id(db, job_id)
            if not job:
                log.error(f"Job {job_id} no encontrado en la base de datos.")
                return

            log.info(f"Iniciando ejecución del Job '{job.name}' (ID: {job.id})")

            # 2. Crear RunHistory como 'RUNNING'
            run = history_manager.start_run(
                db, job_id=job.id, job_name=job.name, trigger_type=trigger
            )
            history_manager.add_log(
                db,
                run.id,
                "INFO",
                f"Iniciando Job: {job.name} (Motor: {job.db_type})",
                stage="init",
            )

            motor = str(job.db_type or "").lower()
            engine_is_sync = str(getattr(job, "engine", None) or "").lower() == "sync"
            is_pure_sync = motor == "sync" or engine_is_sync
            if is_pure_sync:
                job.db_type = "sync"

            # TODO EL PROCESO ENVUELTO EN UN GRAN TRY-EXCEPT CON TIMEOUT
            # Protegemos el pipeline completo con un timeout de 2 horas (7200 segundos)
            # para evitar que se quede en estado RUNNING infinitamente
            staging_paths_to_cleanup: list[Path] = []
            error_msg = ""
            is_success = False
            try:
                if is_pure_sync:
                    file_size, final_dest = await asyncio.wait_for(
                        self._execute_pure_sync(job, run, db),
                        timeout=7200,
                    )
                else:
                    async def pipeline_execution():
                        """Función interna que ejecuta el pipeline completo."""
                        artifact_is_final_delivery = False
                        # Fallback si el frontend envía tipo incorrecto y db_name es directorio
                        if job.db_name:
                            src_path = Path(job.db_name)
                            if src_path.is_dir() and str(job.db_type or "").lower() not in (
                                "folder",
                                "sync",
                            ):
                                job.db_type = "folder"
                                log.warning(
                                    f"Corrigiendo tipo de backup a 'folder' para la ruta: {src_path}"
                                )

                        # Detectar múltiples bases de datos (separadas por comas)
                        # Solo para motores de base de datos reales (postgresql, mysql, sqlserver)
                        db_names = []
                        if job.db_name and job.db_type in ["postgresql", "mysql", "sqlserver"]:
                            if "," in job.db_name:
                                # Múltiples bases de datos
                                db_names = [name.strip() for name in job.db_name.split(",") if name.strip()]
                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    f"Detectadas múltiples bases de datos: {', '.join(db_names)}",
                                    stage="dump",
                                )
                            else:
                                # Base de datos única
                                db_names = [job.db_name]
                        elif job.db_name:
                            # Para otros tipos (sqlite, mdb, folder), usar db_name tal cual
                            db_names = [job.db_name]

                        def _safe_filename_component(value: str, fallback: str = "backup") -> str:
                            cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
                            cleaned = cleaned.strip("._-")
                            return cleaned or fallback

                        # Función interna para procesar una sola base de datos
                        async def process_single_database(
                            db_name_to_process: str,
                            db_index: int = 0,
                            total_dbs: int = 1,
                            output_dir: Path | None = None,
                        ):
                            """Procesa el volcado de una base de datos (opcionalmente dentro de output_dir)."""
                            if total_dbs > 1:
                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    f"Procesando BD {db_index + 1}/{total_dbs}: '{db_name_to_process}' usando conector {job.db_type}...",
                                    stage="dump",
                                )
                            else:
                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    f"Iniciando volcado de la BD '{db_name_to_process}' usando conector {job.db_type}...",
                                    stage="dump",
                                )

                            suffix = ".bak" if job.db_type == "sqlserver" else ".sql"
                            timestamp = run.started_at.strftime("%Y%m%d_%H%M%S")
                            safe_db_name = _safe_filename_component(db_name_to_process, "database")

                            if output_dir is not None:
                                await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)
                                dump_path = output_dir / f"{safe_db_name}_{timestamp}{suffix}"
                                if dump_path.exists():
                                    dump_path.unlink()
                                dump_path_str = str(dump_path)
                            else:
                                fd, dump_path_str = tempfile.mkstemp(suffix=suffix)
                                os.close(fd)
                                dump_path = Path(dump_path_str)

                            original_db_name = job.db_name
                            job.db_name = db_name_to_process

                            if job.db_type == "postgresql":
                                from src.connectors.postgresql import PostgreSQLConnector

                                connector = PostgreSQLConnector()
                                await connector.extract(job, dump_path)

                                if output_dir is None:
                                    final_sql_name = f"{safe_db_name}_{timestamp}.sql"
                                    final_sql_path = dump_path.with_name(final_sql_name)
                                    if final_sql_path.exists():
                                        final_sql_path.unlink()
                                    dump_path = await asyncio.to_thread(dump_path.rename, final_sql_path)

                            elif job.db_type == "mysql":
                                from src.connectors.mysql import MySQLConnector

                                connector = MySQLConnector()
                                await connector.extract(job, dump_path)

                            elif job.db_type == "sqlserver":
                                host_str = (
                                    f"{job.db_host},{job.db_port}"
                                    if job.db_port
                                    else f"{job.db_host}"
                                )
                                cmd = [
                                    "sqlcmd",
                                    "-S",
                                    host_str,
                                    "-U",
                                    job.db_user or "",
                                    "-P",
                                    job.db_password or "",
                                    "-Q",
                                    f"BACKUP DATABASE [{db_name_to_process}] TO DISK='{dump_path_str}'",
                                ]
                                process = subprocess.run(cmd, capture_output=True, text=True)
                                if process.returncode != 0:
                                    raise Exception(
                                        f"Error en sqlcmd: {process.stderr or process.stdout}"
                                    )

                            job.db_name = original_db_name
                            return dump_path

                        # Procesar bases de datos múltiples o única
                        if job.db_type in ["postgresql", "mysql", "sqlserver"] and len(db_names) > 1:
                            timestamp = run.started_at.strftime("%Y%m%d_%H%M%S")
                            safe_job_name = _safe_filename_component(job.name, "tarea")
                            pipeline_staging_root = (
                                Path(tempfile.gettempdir()) / f"solba_staging_{job.id}_{timestamp}"
                            )
                            task_folder = pipeline_staging_root / f"{safe_job_name}_multiple_{timestamp}"
                            await asyncio.to_thread(task_folder.mkdir, parents=True, exist_ok=True)
                            staging_paths_to_cleanup.append(pipeline_staging_root)

                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                f"Volcando {len(db_names)} bases de datos en carpeta temporal unificada...",
                                stage="dump",
                            )

                            for idx, db_name_item in enumerate(db_names):
                                await process_single_database(
                                    db_name_item, idx, len(db_names), output_dir=task_folder
                                )

                            should_compress = getattr(job, "compress", True)

                            if should_compress:
                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    "Comprimiendo todas las bases de datos en un único archivo ZIP...",
                                    stage="compress",
                                )
                                base_name = str(pipeline_staging_root / f"{safe_job_name}_{timestamp}")
                                archive_path_str = await asyncio.to_thread(
                                    shutil.make_archive, base_name, "zip", task_folder
                                )
                                compressed_path = Path(archive_path_str)
                                final_name = f"{safe_job_name}_{timestamp}.zip"
                                final_temp_path = compressed_path.parent / final_name
                                if final_temp_path != compressed_path:
                                    compressed_path = await asyncio.to_thread(
                                        compressed_path.rename, final_temp_path
                                    )
                                file_size = compressed_path.stat().st_size
                                final_dest = str(
                                    Path(job.dest_local_path or str(Path.cwd() / "backups")) / final_name
                                )
                            else:
                                compressed_path = task_folder
                                file_size = sum(
                                    f.stat().st_size
                                    for f in task_folder.rglob("*")
                                    if f.is_file()
                                )
                                final_dest = str(task_folder)

                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                f"Subiendo backup unificado ({file_size} bytes) a destino '{job.dest_type}'...",
                                stage="upload",
                            )

                            if job.dest_type == "local":
                                from src.destinations.local import LocalDestination

                                destination = LocalDestination()
                                dest_path_str = job.dest_local_path or str(Path.cwd() / "backups")
                                await destination.upload(compressed_path, dest_path_str)
                                if should_compress:
                                    final_dest = str(Path(dest_path_str) / compressed_path.name)
                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    f"Backup unificado subido exitosamente a: {final_dest}",
                                    stage="upload",
                                )
                            elif job.dest_type == "google_drive":
                                from src.destinations.google_drive import GoogleDriveDestination

                                destination = GoogleDriveDestination(
                                    folder_id=job.dest_gdrive_folder_id,
                                    retention_days=job.dest_retention_days,
                                    job_name=job.name,
                                )
                                web_link = await asyncio.to_thread(destination.upload, compressed_path)
                                final_dest = web_link
                                if job.dest_retention_days and job.dest_retention_days > 0:
                                    await asyncio.to_thread(destination.apply_retention)
                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    f"Backup unificado subido a Google Drive: {web_link}",
                                    stage="upload",
                                )
                            else:
                                raise NotImplementedError(
                                    f"Destino '{job.dest_type}' no implementado aún."
                                )

                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                f"Procesamiento unificado de {len(db_names)} bases de datos completado.",
                                stage="done",
                            )

                            try:
                                history_manager.add_log(
                                    db, run.id, "INFO", "Iniciando Garbage Collector...", stage="cleanup"
                                )
                                from src.core.cleaner import GarbageCollector

                                global_settings = crud.setting_get_all(db)
                                deleted_total = GarbageCollector.run_retention_policy(db, global_settings)
                                if deleted_total > 0:
                                    history_manager.add_log(
                                        db,
                                        run.id,
                                        "INFO",
                                        f"Garbage Collector: Eliminados {deleted_total} backups antiguos.",
                                        stage="cleanup",
                                    )
                            except Exception as gc_err:
                                log.warning("Error silencioso en Garbage Collector: %s", gc_err)

                            return file_size, final_dest
                        elif job.db_type in ["postgresql", "mysql", "sqlserver"]:
                            # Base de datos única
                            dump_path = await process_single_database(db_names[0], 0, 1)
                        elif job.db_type in ["sqlite", "mdb"]:
                            # Inicializar dump_path para db locales
                            fd, dump_path_str = tempfile.mkstemp(suffix=".sql")
                            os.close(fd)
                            dump_path = Path(dump_path_str)

                            if not job.db_name:
                                raise ValueError(
                                    "Error crítico: El Frontend ha enviado una ruta de origen vacía."
                                )
                            src_file = Path(job.db_name)
                            if not src_file.exists():
                                raise FileNotFoundError(
                                    f"El archivo origen {src_file} no existe."
                                )
                            shutil.copy2(src_file, dump_path)

                        elif job.db_type in ("folder", "sync"):
                            # Carpeta local: 'sync' en BD = Sincronización/espejo (UI job_type_sync);
                            # 'folder' + sin comprimir + retención NULL coincide con el payload que envía el wizard de sync.
                            # Ver: models.Job.db_type, frontend app.js (finalDbType / dest_retention_days isSync).
                            # Inicializar dump_path para carpetas
                            fd, dump_path_str = tempfile.mkstemp(suffix=".tmp")
                            os.close(fd)
                            dump_path = Path(dump_path_str)

                            if not job.db_name:
                                raise ValueError(
                                    "Error crítico: El Frontend ha enviado una ruta de origen vacía."
                                )
                            src_folder = Path(job.db_name)
                        
                            try:
                                if not src_folder.exists() or not src_folder.is_dir():
                                    raise FileNotFoundError(
                                        f"La carpeta origen {src_folder} no existe o no es un directorio."
                                    )
                                # Verificar permisos listando el directorio
                                _ = list(src_folder.iterdir())
                            except PermissionError as e:
                                raise PermissionError(f"Error de permisos al acceder a la ruta de origen: {e}")
                            except OSError as e:
                                if isinstance(e, FileNotFoundError):
                                    raise
                                raise OSError(f"Error al verificar la ruta de origen: {e}")

                            if getattr(job, "compress", True) == False:
                                if job.dest_type == "google_drive":
                                    raise ValueError("No se puede hacer backup de carpeta sin compresión hacia Google Drive.")

                                timestamp = run.started_at.strftime("%Y%m%d_%H%M%S")
                                base_path = Path(job.dest_local_path or Path.cwd() / "backups")
                                _jt = str(job.db_type or "").lower()
                                # Sincronización real: BD sync, o folder mal etiquetado con el mismo perfil que envía la UI de espejo.
                                _tarea_es_sincronizacion_real = _jt == "sync" or (
                                    _jt == "folder"
                                    and str(job.dest_type or "local").lower() == "local"
                                    and job.dest_retention_days is None
                                )
                                if _tarea_es_sincronizacion_real:
                                    dest_path = base_path.resolve()
                                    name_variants = [
                                        job.name.lower(),
                                        job.name.replace(" ", "_").lower(),
                                        job.name.replace("_", " ").lower(),
                                    ]
                                    if dest_path.name.lower() in name_variants:
                                        dest_path = dest_path.parent

                                    def _mirror_espejo_local_sin_zip() -> None:
                                        dest_path.mkdir(parents=True, exist_ok=True)
                                        for item in list(dest_path.iterdir()):
                                            if item.is_dir():
                                                shutil.rmtree(item)
                                            else:
                                                item.unlink()
                                        for item in src_folder.iterdir():
                                            if item.is_dir():
                                                shutil.copytree(item, dest_path / item.name)
                                            else:
                                                shutil.copy2(item, dest_path / item.name)

                                    history_manager.add_log(
                                        db,
                                        run.id,
                                        "INFO",
                                        f"Espejo en destino estricto (sin subcarpeta con timestamp): {src_folder} -> {dest_path}",
                                        stage="dump",
                                    )
                                    await asyncio.to_thread(_mirror_espejo_local_sin_zip)
                                else:
                                    dest_path = base_path / f"{job.name}_{timestamp}"
                                    history_manager.add_log(
                                        db,
                                        run.id,
                                        "INFO",
                                        f"Copiando carpeta cruda directamente (sin compresión): {src_folder} -> {dest_path}",
                                        stage="dump",
                                    )
                                    await asyncio.to_thread(
                                        shutil.copytree, src_folder, dest_path, dirs_exist_ok=True
                                    )
                                dump_path = dest_path
                                artifact_is_final_delivery = True
                            else:
                                # Directorio temporal de empaquetado para sincronización incremental
                                staging_dir = Path(tempfile.gettempdir()) / f"solba_pkg_{job.id}"
                                staging_dir.mkdir(parents=True, exist_ok=True)
                                staging_paths_to_cleanup.append(staging_dir)
                            
                                history_manager.add_log(
                                    db, run.id, "INFO", 
                                    f"Sincronizando carpeta (incremental): {src_folder} -> {staging_dir}", 
                                    stage="dump"
                                )

                                copied = 0
                                updated = 0
                                skipped = 0
                                total = 0

                                try:
                                    for src_path in src_folder.rglob("*"):
                                        if src_path.is_dir():
                                            continue
                                        total += 1
                                        rel = src_path.relative_to(src_folder)
                                        dst_path = staging_dir / rel

                                        if not dst_path.exists():
                                            dst_path.parent.mkdir(parents=True, exist_ok=True)
                                            shutil.copy2(src_path, dst_path)
                                            copied += 1
                                            continue

                                        try:
                                            src_stat = src_path.stat()
                                            dst_stat = dst_path.stat()
                                        except OSError:
                                            shutil.copy2(src_path, dst_path)
                                            updated += 1
                                            continue

                                        if src_stat.st_size == dst_stat.st_size and src_stat.st_mtime <= dst_stat.st_mtime:
                                            skipped += 1
                                            continue

                                        if filecmp.cmp(src_path, dst_path, shallow=False):
                                            skipped += 1
                                            continue

                                        shutil.copy2(src_path, dst_path)
                                        updated += 1
                                except PermissionError as e:
                                    raise PermissionError(f"Error de permisos durante la sincronización: {e}")
                                except Exception as e:
                                    raise RuntimeError(f"Error inesperado durante la sincronización de archivos: {e}")

                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    f"Sincronización incremental finalizada. Total={total}, copiados={copied}, actualizados={updated}, sin cambios={skipped}.",
                                    stage="dump",
                                )

                                # Creamos un archivo .zip con el contenido de la carpeta temporal (staging)
                                # Wrap synchronous make_archive in thread to avoid blocking event loop
                                base_name = str(dump_path.with_suffix(""))
                                archive_path_str = await asyncio.to_thread(shutil.make_archive, base_name, "zip", staging_dir)

                                if dump_path.exists():
                                    dump_path.unlink()

                                dump_path = Path(archive_path_str)

                        else:
                            raise NotImplementedError(
                                f"El conector para el motor '{job.db_type}' no está implementado aún."
                            )

                        if dump_path.is_dir():
                            dump_size = sum(
                                f.stat().st_size for f in dump_path.rglob("*") if f.is_file()
                            )
                        else:
                            dump_size = dump_path.stat().st_size
                        history_manager.add_log(
                            db,
                            run.id,
                            "INFO",
                            f"Volcado completado: {dump_path.name} ({dump_size} bytes)",
                            stage="dump",
                        )

                        # 4. Comprimir el Archivo (condicional basado en job.compress)
                        should_compress = getattr(job, "compress", True)
                    
                        if not artifact_is_final_delivery and should_compress:
                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                "Iniciando compresión en formato ZIP...",
                                stage="compress",
                            )
                            # Wrap synchronous compress in thread to avoid blocking event loop
                            compressed_path = await asyncio.to_thread(self.compressor.compress, dump_path)
                            file_size = compressed_path.stat().st_size
                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                f"Compresión exitosa. Tamaño final: {file_size} bytes.",
                                stage="compress",
                            )
                        elif not artifact_is_final_delivery and not should_compress:
                            # No comprimir: mover archivo a subcarpeta con nombre del backup
                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                "Omitiendo compresión (compress=False). Moviendo archivo a carpeta de backup...",
                                stage="compress",
                            )
                            timestamp_str = run.started_at.strftime("%Y%m%d_%H%M%S")
                            db_name = db_names[0] if db_names else (job.db_name or "unknown")
                            staging_dir = Path(tempfile.gettempdir())
                        
                            final_sql_name = f"{_safe_filename_component(db_name, 'database')}_{timestamp_str}.sql"
                            await asyncio.to_thread(shutil.move, str(dump_path), str(dump_path.parent / final_sql_name))
                        
                            task_folder = staging_dir / f"{job.name}_{db_name}_{timestamp_str}"
                            await asyncio.to_thread(task_folder.mkdir, parents=True, exist_ok=True)
                            staging_paths_to_cleanup.append(task_folder)

                            await asyncio.to_thread(shutil.move, str(dump_path.parent / final_sql_name), str(task_folder / final_sql_name))
                        
                            if job.dest_type == "google_drive":
                                compressed_path = task_folder / final_sql_name
                            else:
                                compressed_path = task_folder
                            file_size = (task_folder / final_sql_name).stat().st_size
                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                f"Archivo movido sin compresión. Tamaño: {file_size} bytes.",
                                stage="compress",
                            )
                        else:
                            compressed_path = dump_path
                            # Calcular el tamaño sumando archivos
                            file_size = sum(f.stat().st_size for f in compressed_path.rglob('*') if f.is_file())

                        # 5. Mover a destino (Carpeta local o red) y 6. Política de retención
                        history_manager.add_log(
                            db,
                            run.id,
                            "INFO",
                            f"Preparando transferencia a destino '{job.dest_type}'...",
                            stage="upload",
                        )

                        # Formatear el nombre del archivo y renombrar el comprimido temporalmente
                        if artifact_is_final_delivery:
                            final_dest = str(compressed_path)
                        else:
                            timestamp = run.started_at.strftime("%Y%m%d_%H%M%S")
                            should_compress = getattr(job, "compress", True)
                        
                            if should_compress:
                                safe_job_name = _safe_filename_component(job.name, "tarea")
                                final_name = f"{safe_job_name}_{timestamp}.zip"
                                final_temp_path = compressed_path.parent / final_name
                                compressed_path = await asyncio.to_thread(compressed_path.rename, final_temp_path)
                                final_dest = str(Path(job.dest_local_path or str(Path.cwd() / "backups")) / final_name)
                            else:
                                # Ya está en la carpeta final, solo necesitamos la ruta
                                final_dest = str(compressed_path)

                        if job.dest_type == "local":
                            from src.destinations.local import LocalDestination

                            destination = LocalDestination()
                            dest_path_str = job.dest_local_path or str(Path.cwd() / "backups")

                            # Subir archivo localmente (omitir si ya quedó en destino: copia cruda / espejo)
                            if not artifact_is_final_delivery:
                                await destination.upload(compressed_path, dest_path_str)

                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                f"Transferencia exitosa a: {final_dest}",
                                stage="upload",
                            )

                            # Retención Local
                            if job.dest_retention_days and job.dest_retention_days > 0:
                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    f"Ejecutando política de retención local ({job.dest_retention_days} días)...",
                                    stage="cleanup",
                                )
                                deleted = await destination.clean_old_backups(
                                    dest_path_str, job.dest_retention_days
                                )
                                if deleted > 0:
                                    history_manager.add_log(
                                        db,
                                        run.id,
                                        "INFO",
                                        f"Borrados {deleted} backups antiguos exitosamente.",
                                        stage="cleanup",
                                    )
                                else:
                                    history_manager.add_log(
                                        db,
                                        run.id,
                                        "INFO",
                                        "No se encontraron backups antiguos que borrar.",
                                        stage="cleanup",
                                    )

                        elif job.dest_type == "google_drive":
                            from src.destinations.google_drive import GoogleDriveDestination

                            destination = GoogleDriveDestination(
                                folder_id=job.dest_gdrive_folder_id,
                                retention_days=job.dest_retention_days,
                                job_name=job.name,
                            )

                            # Subir archivo a GDrive (ejecución síncrona enviada a thread)
                            web_link = await asyncio.to_thread(
                                destination.upload, compressed_path
                            )
                            final_dest = web_link
                            if job.dest_retention_days and job.dest_retention_days > 0:
                                await asyncio.to_thread(destination.apply_retention)
                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                f"Transferencia a Google Drive exitosa. Enlace: {web_link}",
                                stage="upload",
                            )

                            if job.dest_retention_days and job.dest_retention_days > 0:
                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    f"Política de retención ejecutada internamente en Drive ({job.dest_retention_days} días).",
                                    stage="cleanup",
                                )

                        else:
                            raise NotImplementedError(
                                f"Destino '{job.dest_type}' no implementado aún."
                            )

                        # Limpieza de archivos temporales
                        should_compress = getattr(job, "compress", True)
                        if (
                            not artifact_is_final_delivery
                            and should_compress
                        ):
                            if dump_path.exists():
                                dump_path.unlink()
                            if compressed_path.exists():
                                compressed_path.unlink()

                        # =====================================================================
                        # 6.5 Integración Google Drive (Opcional vía Settings)
                        # =====================================================================
                        global_settings = crud.setting_get_all(db)
                        is_cloud_enabled = (
                            str(global_settings.get("cloud_enabled", "false")).lower() == "true"
                        )

                        if is_cloud_enabled:
                            try:
                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    "Iniciando subida a Google Drive...",
                                    stage="cloud_upload",
                                )

                                from src.destinations.google_drive import GoogleDriveDestination

                                # Recogemos las credenciales dinámicamente desde Settings
                                creds_path = global_settings.get(
                                    "credentials_path", "credentials.json"
                                )
                                folder_id = global_settings.get("drive_folder_id", None)

                                drive_dest = GoogleDriveDestination(
                                    credentials_file=creds_path, folder_id=folder_id
                                )

                                # El archivo final se lee directamente desde la ruta en la que quedó tras el volcado local
                                drive_dest.upload(Path(final_dest))

                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    "✅ Subida a Google Drive completada exitosamente.",
                                    stage="cloud_upload",
                                )

                                delete_local = str(global_settings.get("gdrive_delete_local", "false")).lower() == "true"
                                if delete_local:
                                    try:
                                        if Path(final_dest).exists():
                                            Path(final_dest).unlink()
                                            history_manager.add_log(
                                                db,
                                                run.id,
                                                "INFO",
                                                f"🗑️ Archivo local eliminado tras subida a GDrive exitosa.",
                                                stage="cleanup",
                                            )
                                    except Exception as e:
                                        log.error(f"Error borrando archivo local tras subida a GDrive: {e}")
                            except Exception as cloud_err:
                                # Si la nube falla, NO lanzamos la excepción hacia arriba. Es solo un aviso.
                                aviso = f"Aviso: Drive falló, pero el local está a salvo. Detalle: {str(cloud_err)}"
                                log.warning(aviso)
                                history_manager.add_log(
                                    db, run.id, "WARNING", aviso, stage="cloud_upload"
                                )
                        # =====================================================================
                        # =====================================================================
                        # 8. Limpieza Global (Garbage Collector)
                        # =====================================================================
                        try:
                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                "Iniciando Garbage Collector...",
                                stage="cleanup",
                            )
                            from src.core.cleaner import GarbageCollector

                            # Ejecutar política de retención global/DB (Garbage Collector 2.0)
                            deleted_total = GarbageCollector.run_retention_policy(db, global_settings)
                        
                            if deleted_total > 0:
                                history_manager.add_log(
                                    db,
                                    run.id,
                                    "INFO",
                                    f"Garbage Collector: Eliminados {deleted_total} backups antiguos y registros de RunHistory.",
                                    stage="cleanup",
                                )

                        except Exception as gc_err:
                            log.warning(f"Error silencioso en Garbage Collector: {gc_err}")
                            history_manager.add_log(
                                db,
                                run.id,
                                "WARNING",
                                f"Aviso en limpieza global: {gc_err}",
                                stage="cleanup",
                            )
                        # =====================================================================

                        history_manager.add_log(
                            db,
                            run.id,
                            "INFO",
                            "Backup almacenado y pipeline completado.",
                            stage="done",
                        )

                        log.info(f"Job '{job.name}' (ID: {job.id}) finalizado con éxito.")
                    
                        # Retornar file_size y final_dest para usarlos fuera de la función
                        return file_size, str(final_dest)
                
                    # Ejecutar el pipeline con timeout de 2 horas (7200 segundos)
                    file_size, final_dest = await asyncio.wait_for(pipeline_execution(), timeout=7200)
                
                # 7. Actualizar RunHistory a 'SUCCESS' si todo fue bien
                history_manager.finish_run(
                    db,
                    run.id,
                    status="success",
                    file_size_bytes=file_size,
                    backup_file_path=final_dest,
                )
                is_success = True

            except asyncio.TimeoutError:
                # Manejo específico para timeout del pipeline
                error_msg = "El pipeline de backup excedió el tiempo límite de 2 horas (7200 segundos) y fue abortado."
                log.error(error_msg)
                print(error_msg)

                # Registrar el error en base de datos
                history_manager.add_log(db, run.id, "ERROR", error_msg, stage="error")

                # Actualizar RunHistory a 'FAILED'
                history_manager.finish_run(
                    db, run.id, status="failed", error_message=error_msg
                )
                is_success = False

            except Exception as e:
                # 8. Captura global de errores (Si cualquier paso falla)
                error_msg = f"Excepción fatal en el pipeline: {str(e)}"
                log.error(error_msg)
                log.error(traceback.format_exc())
                print(error_msg)  # Imprime por consola por si acaso

                # Registrar el error en base de datos para que la API/Frontend lo vean
                history_manager.add_log(db, run.id, "ERROR", error_msg, stage="error")

                # Actualizar RunHistory a 'FAILED'
                history_manager.finish_run(
                    db, run.id, status="failed", error_message=error_msg
                )
                is_success = False

            finally:
                _safe_staging_cleanup(staging_paths_to_cleanup, job.dest_local_path)

            # =====================================================================
            # 9. Notificaciones Centralizadas (Email + WhatsApp)
            # =====================================================================
            try:
                global_settings = crud.setting_get_all(db)
                notification_email = global_settings.get("notification_email", "")
                
                notify_errors_only = global_settings.get("notify_errors_only", False)
                if isinstance(notify_errors_only, str):
                    notify_errors_only = notify_errors_only.lower() == "true"

                # ── Notificación por Email (SMTP) ──
                if notification_email:
                    if is_success and notify_errors_only:
                        log.info("Omitiendo notificación por email (notify_errors_only está activo y el backup fue exitoso).")
                    else:
                        from src.core.notifications import (
                            format_bytes_display,
                            render_backup_report_html,
                            send_email_notification,
                        )
                        from src.db.models import LogEntry

                        db.refresh(run)
    
                        # Recuperar logs de la base de datos para incluirlos en el correo
                        log_entries = db.query(LogEntry).filter(LogEntry.run_id == run.id).order_by(LogEntry.timestamp.asc()).all()
                        log_lines = [f"[{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] [{entry.level}] {entry.message}" for entry in log_entries]
                        
                        if len(log_lines) > 100:
                            log_lines = log_lines[-100:]
                            
                        log_text = "\n".join(log_lines)
                        log_section = f"\n\n--- LOGS DE EJECUCIÓN ---\n\n{log_text}" if log_text else "\n\n--- LOGS DE EJECUCIÓN ---\n\n(No hay logs disponibles)"
    
                        trigger_label = {
                            "manual": "Manual",
                            "scheduled": "Programada (Windows)",
                        }.get((trigger or "").lower(), trigger or "Manual")

                        dest_summary = (
                            f"Google Drive (carpeta ID: {job.dest_gdrive_folder_id or 'N/D'})"
                            if (job.dest_type or "").lower() == "google_drive"
                            else (job.dest_local_path or "N/D")
                        )
                        html_content = render_backup_report_html(
                            success=is_success,
                            job_name=job.name,
                            job_id=job.id,
                            db_type=str(job.db_type or ""),
                            destination_summary=dest_summary,
                            log_lines=log_lines,
                            error_message=(None if is_success else error_msg),
                            size_display=format_bytes_display(run.file_size_bytes),
                        )

                        if is_success:
                            send_email_notification(
                                to_email=notification_email,
                                subject=f"Backup exitoso: {job.name}",
                                body=(
                                    f"El trabajo de backup '{job.name}' (ID: {job.id}) finalizó "
                                    f"correctamente. Tipo de ejecución: {trigger_label}."
                                    f"{log_section}"
                                ),
                                html_body=html_content,
                            )
                        else:
                            send_email_notification(
                                to_email=notification_email,
                                subject=f"Error en backup: {job.name}",
                                body=(
                                    f"El trabajo de backup '{job.name}' (ID: {job.id}) ha fallado. "
                                    f"Tipo de ejecución: {trigger_label}.\n\n"
                                    f"Detalle del error:\n{error_msg}\n\n"
                                    f"Revise los logs en el panel."
                                    f"{log_section}"
                                ),
                                html_body=html_content,
                            )

                # ── Notificación por WhatsApp (ApiWhatsApp Outbox) ──
                try:
                    from src.notifications.whatsapp import whatsapp_notifier
                    whatsapp_notifier.send_backup_status(
                        job_name=job.name,
                        trigger=trigger,
                        success=is_success,
                    )
                except Exception as wa_exc:
                    log.error(f"❌ Error inesperado al encolar notificación WhatsApp: {wa_exc}")

            except Exception as notif_err:
                log.error(f"Error general en el bloque de notificaciones: {notif_err}")
            # =====================================================================

    async def execute_job(self, job_id: int, trigger: str = "manual") -> None:
        """Public entry point; identical to :meth:`run_job`.

        Args:
            job_id: Database id of the job to execute.
            trigger: Origin of the run.

        Returns:
            ``None``.
        """
        await self.run_job(job_id, trigger=trigger)
