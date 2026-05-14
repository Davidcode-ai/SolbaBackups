"""
src/core/job_manager.py — Orquestador del Pipeline de Backup.

Contiene la lógica central del JobManager que une la base de datos,
los conectores, compresores y destinos.
"""

import logging
import filecmp
import os
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


class JobManager:
    """
    Orquesta la ejecución de un Job de backup (Pipeline completo).
    """

    def __init__(self):
        """
        Inicializa el JobManager.

        Instancia el compresor predeterminado (ZIP) que se utilizará
        para reducir el tamaño de los volcados SQL extraídos.
        """
        self.compressor = Compressor()

    def restore_backup(self, run_id: int) -> dict:
        """
        Restaura un backup previamente generado a partir de un run exitoso.

        Flujo:
        1) Localiza el archivo comprimido asociado al run.
        2) Descomprime en carpeta temporal.
        3) Ejecuta restauración según db_type (postgresql/mysql).
        4) Registra progreso y errores en los logs del mismo run_id.
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
                # Es un backup local
                backup_path = Path(backup_file_path)
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
                with tempfile.TemporaryDirectory(prefix="solba_restore_") as tmp_dir:
                    tmp_dir_path = Path(tmp_dir)
                    extracted_sql_path: Path | None = None

                    history_manager.add_log(
                        db,
                        run_id,
                        "INFO",
                        "Descomprimiendo backup en carpeta temporal...",
                        stage="restore_extract",
                    )

                    if zipfile.is_zipfile(backup_path):
                        with zipfile.ZipFile(backup_path, "r") as zf:
                            zf.extractall(tmp_dir_path)

                    db_type = (job.db_type or "").lower()
                    
                    # Detectar archivo/carpeta a restaurar según el tipo
                    extracted_path: Path | None = None
                    
                    if db_type in ["postgresql", "mysql"]:
                        sql_candidates = sorted(tmp_dir_path.rglob("*.sql"))
                        if sql_candidates:
                            extracted_path = sql_candidates[0]
                        else:
                            extracted_files = [p for p in tmp_dir_path.rglob("*") if p.is_file()]
                            if len(extracted_files) == 1:
                                extracted_path = extracted_files[0]
                    elif db_type == "sqlite":
                        db_candidates = sorted(tmp_dir_path.rglob("*.db"))
                        if db_candidates:
                            extracted_path = db_candidates[0]
                        else:
                            db_candidates = sorted(tmp_dir_path.rglob("*.sqlite"))
                            if db_candidates:
                                extracted_path = db_candidates[0]
                            else:
                                db_candidates = sorted(tmp_dir_path.rglob("*.sqlite3"))
                                if db_candidates:
                                    extracted_path = db_candidates[0]
                    elif db_type == "folder":
                        extracted_path = tmp_dir_path
                        top_level = [
                            p for p in tmp_dir_path.iterdir() if p.name not in ("__MACOSX",)
                        ]
                        if len(top_level) == 1 and top_level[0].is_dir():
                            extracted_path = top_level[0]
                        else:
                            zip_candidates = sorted(
                                [p for p in tmp_dir_path.rglob("*.zip") if p.is_file()]
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

                        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
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

                        with extracted_path.open("r", encoding="utf-8", errors="ignore") as sql_fp:
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

                    elif db_type == "sqlite":
                        if not job.db_name:
                            raise ValueError(
                                "Falta la ruta del archivo de base de datos SQLite (db_name)."
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
                            f"Sobrescribiendo archivo SQLite original: {original_db_path}",
                            stage="restore_execute",
                        )

                        try:
                            shutil.copy2(extracted_path, original_db_path)
                            history_manager.add_log(
                                db,
                                run_id,
                                "INFO",
                                f"Archivo SQLite restaurado exitosamente.",
                                stage="restore_execute",
                            )
                        except PermissionError as perm_err:
                            raise RuntimeError(
                                f"Error de permisos al sobrescribir archivo SQLite: {perm_err}"
                            )

                    elif db_type == "folder":
                        if not job.db_name:
                            raise ValueError(
                                "Falta la ruta de la carpeta original (db_name)."
                            )

                        original_folder_path = Path(job.db_name)
                        if not original_folder_path.exists() or not original_folder_path.is_dir():
                            raise FileNotFoundError(
                                f"La carpeta original no existe: {original_folder_path}"
                            )

                        history_manager.add_log(
                            db,
                            run_id,
                            "INFO",
                            f"Restaurando contenido de carpeta: {original_folder_path}",
                            stage="restore_execute",
                        )

                        try:
                            if not extracted_path or not Path(extracted_path).is_dir():
                                raise FileNotFoundError(
                                    "No se pudo localizar el contenido descomprimido de la carpeta para restaurar."
                                )
                            shutil.copytree(extracted_path, original_folder_path, dirs_exist_ok=True)
                            history_manager.add_log(
                                db,
                                run_id,
                                "INFO",
                                f"Carpeta restaurada exitosamente.",
                                stage="restore_execute",
                            )
                        except PermissionError as perm_err:
                            raise RuntimeError(
                                f"Error de permisos al restaurar carpeta: {perm_err}"
                            )

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

    async def run_job(self, job_id: int, trigger: str = "manual") -> None:
        """
        Ejecuta el pipeline de backup completo para un Job específico.

        Este método orquesta la extracción (dump), compresión, transferencia
        al destino final y la política de retención. Gestiona su propia
        sesión de base de datos para no bloquear el hilo principal.

        Args:
            job_id (int): El identificador único del Job en la base de datos.
            trigger (str, optional): El origen de la ejecución ('manual', 'interval', 'cron').
                                     Por defecto es "manual".

        Returns:
            None

        Raises:
            Exception: Atrapa internamente cualquier excepción durante el pipeline,
                       la registra en los logs de la ejecución y marca el RunHistory
                       como 'FAILED'. No propaga la excepción hacia arriba.
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

            # TODO EL PROCESO ENVUELTO EN UN GRAN TRY-EXCEPT
            try:
                # REFACTORIZACIÓN DE EMERGENCIA: Fallback si el frontend falla
                if job.db_name:
                    src_path = Path(job.db_name)
                    if src_path.is_dir() and job.db_type != "folder":
                        job.db_type = "folder"
                        log.warning(
                            f"Corrigiendo tipo de backup a 'folder' para la ruta: {src_path}"
                        )

                # 3. Extracción de BD (Dump)
                history_manager.add_log(
                    db,
                    run.id,
                    "INFO",
                    f"Iniciando volcado de la BD '{job.db_name}' usando conector {job.db_type}...",
                    stage="dump",
                )

                # Archivo temporal por defecto
                suffix = ".bak" if job.db_type == "sqlserver" else ".sql"
                if job.db_type == "folder":
                    suffix = ".tmp"

                fd, dump_path_str = tempfile.mkstemp(suffix=suffix)
                os.close(fd)
                dump_path = Path(dump_path_str)

                # Seleccionar y ejecutar conector
                if job.db_type == "postgresql":
                    from src.connectors.postgresql import PostgreSQLConnector

                    connector = PostgreSQLConnector()
                    await connector.extract(job, dump_path)

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
                        f"BACKUP DATABASE [{job.db_name}] TO DISK='{dump_path_str}'",
                    ]
                    process = subprocess.run(cmd, capture_output=True, text=True)
                    if process.returncode != 0:
                        raise Exception(
                            f"Error en sqlcmd: {process.stderr or process.stdout}"
                        )

                elif job.db_type in ["sqlite", "mdb"]:
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

                elif job.db_type == "folder":
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

                    # Directorio temporal de empaquetado para sincronización incremental
                    staging_dir = Path(tempfile.gettempdir()) / f"solba_pkg_{job.id}"
                    staging_dir.mkdir(parents=True, exist_ok=True)
                    
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
                    base_name = str(dump_path.with_suffix(""))
                    archive_path_str = shutil.make_archive(base_name, "zip", staging_dir)

                    if dump_path.exists():
                        dump_path.unlink()

                    dump_path = Path(archive_path_str)

                elif job.db_type == "sync":
                    if not job.db_name:
                        raise ValueError("Error crítico: El Frontend ha enviado una ruta de origen vacía.")
                    src_folder = Path(job.db_name)
                    if not src_folder.exists() or not src_folder.is_dir():
                        raise FileNotFoundError(f"La carpeta origen {src_folder} no existe.")
                        
                    if dump_path.exists():
                        dump_path.unlink()
                        
                    dest_sync_folder = Path(job.dest_local_path) / job.name if job.dest_local_path else Path.cwd() / "backups" / job.name
                    history_manager.add_log(db, run.id, "INFO", f"Sincronizando carpeta (incremental): {src_folder} -> {dest_sync_folder}", stage="dump")
                    dest_sync_folder.mkdir(parents=True, exist_ok=True)

                    copied = 0
                    updated = 0
                    skipped = 0
                    total = 0

                    for src_path in src_folder.rglob("*"):
                        if src_path.is_dir():
                            continue
                        total += 1
                        rel = src_path.relative_to(src_folder)
                        dst_path = dest_sync_folder / rel

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

                    history_manager.add_log(
                        db,
                        run.id,
                        "INFO",
                        f"Sincronización incremental finalizada. Total={total}, copiados={copied}, actualizados={updated}, sin cambios={skipped}.",
                        stage="dump",
                    )
                    log.info(
                        "SYNC incremental %s -> %s | total=%d, copiados=%d, actualizados=%d, sin cambios=%d",
                        src_folder,
                        dest_sync_folder,
                        total,
                        copied,
                        updated,
                        skipped,
                    )
                    
                    dump_path = dest_sync_folder

                else:
                    raise NotImplementedError(
                        f"El conector para el motor '{job.db_type}' no está implementado aún."
                    )

                dump_size = dump_path.stat().st_size
                history_manager.add_log(
                    db,
                    run.id,
                    "INFO",
                    f"Volcado completado: {dump_path.name} ({dump_size} bytes)",
                    stage="dump",
                )

                # 4. Comprimir el Archivo
                if job.db_type != "sync":
                    history_manager.add_log(
                        db,
                        run.id,
                        "INFO",
                        "Iniciando compresión en formato ZIP...",
                        stage="compress",
                    )
                    compressed_path = self.compressor.compress(dump_path)
                    file_size = compressed_path.stat().st_size
                    history_manager.add_log(
                        db,
                        run.id,
                        "INFO",
                        f"Compresión exitosa. Tamaño final: {file_size} bytes.",
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
                if job.db_type != "sync":
                    timestamp = run.started_at.strftime("%Y%m%d_%H%M%S")
                    final_name = f"{job.name}_{timestamp}.sql.zip"
                    final_temp_path = compressed_path.parent / final_name
                    compressed_path = compressed_path.rename(final_temp_path)
                    final_dest = str(Path(job.dest_local_path or str(Path.cwd() / "backups")) / final_name)
                else:
                    final_dest = str(compressed_path)

                if job.dest_type == "local":
                    from src.destinations.local import LocalDestination

                    destination = LocalDestination()
                    dest_path_str = job.dest_local_path or str(Path.cwd() / "backups")

                    # Subir archivo localmente
                    if job.db_type != "sync":
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
                    import asyncio

                    # Subir archivo a GDrive (ejecución síncrona enviada a thread)
                    web_link = await asyncio.to_thread(
                        destination.upload, compressed_path
                    )
                    final_dest = web_link
                    history_manager.add_log(
                        db,
                        run.id,
                        "INFO",
                        f"Transferencia a Google Drive exitosa. Enlace: {web_link}",
                        stage="upload",
                    )

                    # La retención de GDrive se ejecuta automáticamente dentro de destination.upload
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
                if job.db_type != "sync":
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

                        if job.db_type == "sync":
                            log.warning("Google Drive no soporta carpetas 'sync' enteras de forma nativa todavía. Omitiendo subida.")
                        else:
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

                # 7. Actualizar RunHistory a 'SUCCESS' si todo fue bien
                history_manager.finish_run(
                    db,
                    run.id,
                    status="success",
                    file_size_bytes=file_size,
                    backup_file_path=str(final_dest),
                )
                log.info(f"Job '{job.name}' (ID: {job.id}) finalizado con éxito.")
                is_success = True

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
                        from src.core.notifications import send_email_notification
                        from src.db.models import LogEntry
    
                        # Recuperar logs de la base de datos para incluirlos en el correo
                        log_entries = db.query(LogEntry).filter(LogEntry.run_id == run.id).order_by(LogEntry.timestamp.asc()).all()
                        log_lines = [f"[{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] [{entry.level}] {entry.message}" for entry in log_entries]
                        
                        if len(log_lines) > 100:
                            log_lines = log_lines[-100:]
                            
                        log_text = "\n".join(log_lines)
                        log_section = f"\n\n--- LOGS DE EJECUCIÓN ---\n\n{log_text}" if log_text else "\n\n--- LOGS DE EJECUCIÓN ---\n\n(No hay logs disponibles)"
    
                        if is_success:
                            send_email_notification(
                                to_email=notification_email,
                                subject=f"✅ Backup Exitoso: {job.name}",
                                body=(
                                    f"El trabajo de backup '{job.name}' (ID: {job.id}) finalizó "
                                    f"correctamente en su ejecución de tipo '{trigger}'."
                                    f"{log_section}"
                                ),
                            )
                        else:
                            send_email_notification(
                                to_email=notification_email,
                                subject=f"❌ Error en Backup: {job.name}",
                                body=(
                                    f"El trabajo de backup '{job.name}' (ID: {job.id}) ha fallado "
                                    f"en su ejecución de tipo '{trigger}'.\n\n"
                                    f"Detalle del error:\n{error_msg}\n\n"
                                f"Revise los logs en el panel."
                                f"{log_section}"
                            ),
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
