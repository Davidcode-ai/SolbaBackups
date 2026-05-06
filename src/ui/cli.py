"""
Interfaz de línea de comandos (CLI) de SolbaBackups.

Comandos:
  backup   sqlite|postgresql|mysql|sqlserver|mdb|folder ...
  restore  sqlite|postgresql|mysql|sqlserver|mdb|folder ...
  detect   --host <ip>
  sync     --source <dir> --dest <dir> [--mode mirror|update|watch]
  upload   --file <path> [--folder-id <id>]
  schedule --list | --run
  status   Muestra el espacio usado por los backups locales
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from tabulate import tabulate

from src.config.settings import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("solba.cli")


# ==========================================================================
# Grupo principal
# ==========================================================================
@click.group()
@click.version_option("1.0.0", prog_name="SolbaBackups")
def main_cli():
    """SolbaBackups – Gestor de copias de seguridad de bases de datos y carpetas."""


# ==========================================================================
# BACKUP
# ==========================================================================
@main_cli.group("backup")
def backup_group():
    """Realiza una copia de seguridad."""


@backup_group.command("sqlite")
@click.option("--db", required=True, help="Ruta al archivo SQLite.")
@click.option("--compression", default=settings.compression, show_default=True)
def backup_sqlite(db: str, compression: str):
    """Copia de seguridad de una base de datos SQLite."""
    from src.backup.sqlite_backup import SQLiteBackup

    bk = SQLiteBackup(settings.backup_dir, compression=compression)
    result = bk.backup(db_path=db)
    _print_result(result)


@backup_group.command("postgresql")
@click.option("--host", default="localhost", show_default=True)
@click.option("--port", default=5432, show_default=True)
@click.option("--db", required=True, help="Nombre de la base de datos.")
@click.option("--user", default="postgres", show_default=True)
@click.option("--password", default="", prompt=False, hide_input=True)
@click.option("--compression", default=settings.compression, show_default=True)
def backup_postgresql(host, port, db, user, password, compression):
    """Copia de seguridad de una base de datos PostgreSQL."""
    from src.backup.postgresql_backup import PostgreSQLBackup

    bk = PostgreSQLBackup(settings.backup_dir, compression=compression)
    result = bk.backup(host=host, port=port, database=db, user=user, password=password)
    _print_result(result)


@backup_group.command("mysql")
@click.option("--host", default="localhost", show_default=True)
@click.option("--port", default=3306, show_default=True)
@click.option("--db", required=True, help="Nombre de la base de datos.")
@click.option("--user", default="root", show_default=True)
@click.option("--password", default="", prompt=False, hide_input=True)
@click.option("--compression", default=settings.compression, show_default=True)
def backup_mysql(host, port, db, user, password, compression):
    """Copia de seguridad de una base de datos MySQL/MariaDB."""
    from src.backup.sql_backup import MySQLBackup

    bk = MySQLBackup(settings.backup_dir, compression=compression)
    result = bk.backup(host=host, port=port, database=db, user=user, password=password)
    _print_result(result)


@backup_group.command("sqlserver")
@click.option("--host", default="localhost", show_default=True)
@click.option("--port", default=1433, show_default=True)
@click.option("--db", required=True, help="Nombre de la base de datos.")
@click.option("--user", default="sa", show_default=True)
@click.option("--password", default="", prompt=False, hide_input=True)
@click.option(
    "--server-bak-path",
    default="",
    help="Ruta en el servidor donde SQL Server puede escribir el .bak.",
)
@click.option("--compression", default=settings.compression, show_default=True)
def backup_sqlserver(host, port, db, user, password, server_bak_path, compression):
    """Copia de seguridad de una base de datos SQL Server."""
    from src.backup.sql_backup import SQLServerBackup

    bk = SQLServerBackup(settings.backup_dir, compression=compression)
    result = bk.backup(
        host=host,
        port=port,
        database=db,
        user=user,
        password=password,
        server_backup_path=server_bak_path,
    )
    _print_result(result)


@backup_group.command("mdb")
@click.option("--db", required=True, help="Ruta al archivo .mdb o .accdb.")
@click.option("--password", default="", hide_input=True)
@click.option("--compression", default=settings.compression, show_default=True)
def backup_mdb(db, password, compression):
    """Copia de seguridad de una base de datos Microsoft Access (MDB/ACCDB)."""
    from src.backup.mdb_backup import MDBBackup

    bk = MDBBackup(settings.backup_dir, compression=compression)
    result = bk.backup(db_path=db, password=password)
    _print_result(result)


@backup_group.command("folder")
@click.option("--source", required=True, help="Carpeta a respaldar.")
@click.option(
    "--incremental", is_flag=True, help="Solo copia archivos nuevos/modificados."
)
@click.option("--exclude", multiple=True, help="Patrones glob a excluir (repetible).")
@click.option("--compression", default=settings.compression, show_default=True)
def backup_folder(source, incremental, exclude, compression):
    """Copia de seguridad de una carpeta de ficheros."""
    from src.backup.folder_backup import FolderBackup

    bk = FolderBackup(settings.backup_dir, compression=compression)
    result = bk.backup(
        source_dir=source,
        incremental=incremental,
        exclude_patterns=list(exclude),
    )
    _print_result(result)


# ==========================================================================
# RESTORE
# ==========================================================================
@main_cli.group("restore")
def restore_group():
    """Restaura una copia de seguridad."""


@restore_group.command("sqlite")
@click.option("--backup", required=True, help="Ruta al archivo de backup.")
@click.option("--target", required=True, help="Ruta destino de la BD.")
def restore_sqlite(backup, target):
    """Restaura una base de datos SQLite."""
    from src.restore.restore_manager import RestoreManager

    rm = RestoreManager()
    result = rm.restore_sqlite(Path(backup), Path(target))
    _print_restore_result(result)


@restore_group.command("postgresql")
@click.option("--backup", required=True)
@click.option("--host", default="localhost", show_default=True)
@click.option("--port", default=5432, show_default=True)
@click.option("--db", required=True)
@click.option("--user", default="postgres", show_default=True)
@click.option("--password", default="", hide_input=True)
@click.option("--create-db", is_flag=True)
def restore_postgresql(backup, host, port, db, user, password, create_db):
    """Restaura una base de datos PostgreSQL."""
    from src.restore.restore_manager import RestoreManager

    rm = RestoreManager()
    result = rm.restore_postgresql(
        Path(backup),
        host=host,
        port=port,
        database=db,
        user=user,
        password=password,
        create_db=create_db,
    )
    _print_restore_result(result)


@restore_group.command("mysql")
@click.option("--backup", required=True)
@click.option("--host", default="localhost", show_default=True)
@click.option("--port", default=3306, show_default=True)
@click.option("--db", required=True)
@click.option("--user", default="root", show_default=True)
@click.option("--password", default="", hide_input=True)
@click.option("--create-db", is_flag=True)
def restore_mysql(backup, host, port, db, user, password, create_db):
    """Restaura una base de datos MySQL/MariaDB."""
    from src.restore.restore_manager import RestoreManager

    rm = RestoreManager()
    result = rm.restore_mysql(
        Path(backup),
        host=host,
        port=port,
        database=db,
        user=user,
        password=password,
        create_db=create_db,
    )
    _print_restore_result(result)


@restore_group.command("folder")
@click.option("--backup", required=True, help="Ruta al backup (.zip / .tar.gz).")
@click.option("--target", required=True, help="Directorio destino.")
@click.option("--no-overwrite", is_flag=True)
def restore_folder(backup, target, no_overwrite):
    """Restaura una carpeta de ficheros."""
    from src.restore.restore_manager import RestoreManager

    rm = RestoreManager()
    result = rm.restore_folder(Path(backup), Path(target), overwrite=not no_overwrite)
    _print_restore_result(result)


# ==========================================================================
# DETECT
# ==========================================================================
@main_cli.command("detect")
@click.option("--host", default="127.0.0.1", show_default=True, help="IP o hostname.")
@click.option(
    "--nmap", "use_nmap", is_flag=True, help="Usar nmap para análisis avanzado."
)
@click.option(
    "--local",
    "scan_local",
    is_flag=True,
    help="Buscar archivos SQLite/MDB en el sistema local.",
)
@click.option(
    "--search-dir",
    multiple=True,
    help="Directorios donde buscar archivos de BD (--local).",
)
def detect(host, use_nmap, scan_local, search_dir):
    """Detecta bases de datos activas en una máquina."""
    from src.detector.db_detector import DatabaseDetector

    detector = DatabaseDetector(timeout=1.5)

    click.echo(f"\n🔍 Escaneando {host}...")
    net_results = detector.detect_network(host=host, use_nmap=use_nmap)
    if net_results:
        headers = ["Base de datos", "Host", "Puerto", "Estado"]
        rows = [[r["db"], r["host"], r["port"], r["status"]] for r in net_results]
        click.echo("\n📡 Servicios de BD detectados en red:")
        click.echo(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
    else:
        click.echo("  No se detectaron servicios de BD en red.")

    if scan_local:
        dirs = list(search_dir) or None
        local_results = detector.detect_local_files(search_dirs=dirs)
        if local_results:
            headers = ["Tipo", "Ruta", "Tamaño (bytes)"]
            rows = [[r["db"], r["path"], r["size_bytes"]] for r in local_results]
            click.echo("\n📂 Archivos de BD locales encontrados:")
            click.echo(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
        else:
            click.echo("  No se encontraron archivos de BD locales.")


# ==========================================================================
# SYNC
# ==========================================================================
@main_cli.command("sync")
@click.option("--source", required=True, help="Carpeta origen.")
@click.option("--dest", required=True, help="Carpeta destino.")
@click.option(
    "--mode",
    type=click.Choice(["mirror", "update", "watch"], case_sensitive=False),
    default="update",
    show_default=True,
)
@click.option("--exclude", multiple=True, help="Patrones glob a excluir.")
def sync_cmd(source, dest, mode, exclude):
    """Sincroniza dos carpetas (unidireccional)."""
    from src.sync.folder_sync import FolderSync

    fs = FolderSync(
        source=Path(source),
        destination=Path(dest),
        mode=mode,
        exclude_patterns=list(exclude),
    )

    if mode == "watch":
        click.echo(
            f"👁️  Monitorización activa: {source} → {dest}  (Ctrl+C para detener)"
        )
        fs.start_watch()
        try:
            import time

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            fs.stop_watch()
    else:
        copied, updated, deleted = fs.sync()
        click.echo(
            f"✅ Sync completado: {copied} copiados, {updated} actualizados, "
            f"{deleted} eliminados."
        )


# ==========================================================================
# UPLOAD (Google Drive)
# ==========================================================================
@main_cli.command("upload")
@click.option("--file", "file_path", required=True, help="Archivo a subir.")
@click.option(
    "--folder-id",
    default=settings.google_drive.get("folder_id", ""),
    help="ID de la carpeta de Google Drive.",
)
@click.option(
    "--credentials",
    default=settings.google_drive.get("credentials_file", "credentials.json"),
    help="Archivo de credenciales OAuth2.",
)
def upload_cmd(file_path, folder_id, credentials):
    """Sube un archivo a Google Drive."""
    from src.storage.google_drive import GoogleDriveUploader

    uploader = GoogleDriveUploader(credentials_file=credentials)
    fid = uploader.upload_backup(Path(file_path), root_folder_id=folder_id)
    if fid:
        click.echo(f"✅ Archivo subido. ID en Drive: {fid}")
    else:
        click.echo("❌ Error al subir el archivo.", err=True)
        sys.exit(1)


# ==========================================================================
# STATUS
# ==========================================================================
@main_cli.command("status")
def status_cmd():
    """Muestra el estado del directorio de backups locales."""
    from src.storage.local_storage import LocalStorage

    storage = LocalStorage(settings.backup_dir)
    usage = storage.disk_usage()
    backups = storage.list_backups()

    click.echo(f"\n📁 Directorio de backups: {settings.backup_dir}")
    click.echo(
        f"   Archivos: {usage['files']}  |  "
        f"Espacio: {usage['total_bytes'] / 1024 / 1024:.2f} MB"
    )

    if backups:
        headers = ["Nombre", "Tamaño (KB)", "Modificado"]
        rows = [
            [
                b["name"],
                f"{b['size_bytes']/1024:.1f}",
                b["modified"].strftime("%Y-%m-%d %H:%M"),
            ]
            for b in backups
        ]
        click.echo(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
    else:
        click.echo("  No hay backups registrados.")


# ==========================================================================
# Helpers
# ==========================================================================
def _print_result(result) -> None:
    if result.success:
        click.echo(
            f"✅ Copia completada:\n"
            f"   Fuente : {result.source}\n"
            f"   Archivo: {result.destination}\n"
            f"   Tamaño : {result.size_bytes / 1024:.1f} KB"
        )
    else:
        click.echo(f"❌ Error en la copia: {result.error}", err=True)
        sys.exit(1)


def _print_restore_result(result) -> None:
    if result.success:
        click.echo(f"✅ Restauración completada → {result.target}")
    else:
        click.echo(f"❌ Error en la restauración: {result.error}", err=True)
        sys.exit(1)
