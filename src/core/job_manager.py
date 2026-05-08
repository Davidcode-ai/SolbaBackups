"""
src/core/job_manager.py — Orquestador del Pipeline de Backup.

Contiene la lógica central del JobManager que une la base de datos,
los conectores, compresores y destinos.
"""

import logging
import os
import shutil
import subprocess
import tempfile
import traceback
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
                    if not src_folder.exists() or not src_folder.is_dir():
                        raise FileNotFoundError(
                            f"La carpeta origen {src_folder} no existe."
                        )

                    # Creamos un archivo .zip con el contenido de la carpeta
                    # shutil.make_archive agrega automáticamente la extensión .zip al base_name
                    base_name = str(dump_path.with_suffix(""))
                    archive_path_str = shutil.make_archive(base_name, "zip", src_folder)

                    # Eliminamos el archivo temporal vacío (.tmp) generado por mkstemp
                    if dump_path.exists():
                        dump_path.unlink()

                    # Actualizamos dump_path para que apunte al .zip real generado
                    dump_path = Path(archive_path_str)

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

                # 5. Mover a destino (Carpeta local o red) y 6. Política de retención
                history_manager.add_log(
                    db,
                    run.id,
                    "INFO",
                    f"Preparando transferencia a destino '{job.dest_type}'...",
                    stage="upload",
                )

                # Formatear el nombre del archivo y renombrar el comprimido temporalmente
                timestamp = run.started_at.strftime("%Y%m%d_%H%M%S")
                final_name = f"{job.name}_{timestamp}.sql.zip"
                final_temp_path = compressed_path.parent / final_name
                compressed_path = compressed_path.rename(final_temp_path)

                if job.dest_type == "local":
                    from src.destinations.local import LocalDestination

                    destination = LocalDestination()
                    dest_path_str = job.dest_local_path or str(Path.cwd() / "backups")

                    # Subir archivo localmente
                    await destination.upload(compressed_path, dest_path_str)

                    final_dest = str(Path(dest_path_str) / final_name)
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

                    local_retention = int(
                        global_settings.get("local_retention_days") or 7
                    )
                    cloud_retention = int(
                        global_settings.get("cloud_retention_days") or 30
                    )

                    # 8.1 Limpieza Local
                    deleted_local = GarbageCollector.clean_local_backups(
                        local_retention
                    )
                    if deleted_local > 0:
                        history_manager.add_log(
                            db,
                            run.id,
                            "INFO",
                            f"Garbage Collector local: Eliminados {deleted_local} backups antiguos.",
                            stage="cleanup",
                        )

                    # 8.2 Limpieza en la Nube (si está habilitado)
                    if is_cloud_enabled:
                        creds_path = global_settings.get(
                            "credentials_path", "credentials.json"
                        )
                        folder_id = global_settings.get("drive_folder_id", None)
                        deleted_cloud = GarbageCollector.clean_cloud_backups(
                            cloud_retention, creds_path, folder_id
                        )
                        if deleted_cloud > 0:
                            history_manager.add_log(
                                db,
                                run.id,
                                "INFO",
                                f"Garbage Collector nube: Eliminados {deleted_cloud} backups antiguos.",
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

                # =====================================================================
                # 9. Notificación SMTP (Opcional vía Settings)
                # =====================================================================
                try:
                    global_settings = crud.setting_get_all(db)
                    smtp_enabled = (
                        str(global_settings.get("smtp_enabled", "false")).lower()
                        == "true"
                    )

                    if smtp_enabled:
                        smtp_host = global_settings.get("smtp_host", "")
                        smtp_port = int(global_settings.get("smtp_port", 587))
                        smtp_user = global_settings.get("smtp_user", "")
                        smtp_password = global_settings.get("smtp_password", "")
                        alert_email_to = global_settings.get("alert_email_to", "")

                        if smtp_host and smtp_user and alert_email_to:
                            from src.notifications.mailer import EmailNotifier

                            notifier = EmailNotifier(
                                host=smtp_host,
                                port=smtp_port,
                                user=smtp_user,
                                password=smtp_password,
                                to_email=alert_email_to,
                            )
                            # Extraer logs de la BD para adjuntarlos (opcional pero útil)
                            logs_entries = crud.log_get_by_run(db, run.id)
                            logs_text = "\n".join(
                                [
                                    f"[{l.stage}] {l.level}: {l.message}"
                                    for l in logs_entries
                                ]
                            )

                            # Disparar correo asíncronamente
                            await notifier.send_failure_alert(
                                job_name=job.name,
                                error_message=error_msg,
                                logs=logs_text,
                            )
                        else:
                            log.warning(
                                "SMTP habilitado pero faltan credenciales (host, user o to_email)."
                            )
                except Exception as smtp_err:
                    log.error(
                        f"Error al intentar enviar el email de alerta SMTP: {smtp_err}"
                    )
                # =====================================================================
