"""
Módulo de restauración de copias de seguridad.

Soporta:
  - SQLite    : reemplaza el archivo de BD con la copia.
  - PostgreSQL: usa pg_restore / psql para restaurar el volcado.
  - MySQL     : usa mysql client para importar el volcado SQL.
  - SQL Server: ejecuta RESTORE DATABASE con sqlcmd.
  - MDB       : copia el archivo de vuelta a la ubicación original.
  - Carpeta   : descomprime y sobreescribe el directorio de destino.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import subprocess
import zipfile
import tarfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RestoreResult:
    """Resultado de una operación de restauración."""

    def __init__(
        self,
        success: bool,
        target: str,
        error: Optional[str] = None,
    ) -> None:
        self.success = success
        self.target = target
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover
        status = "OK" if self.success else f"ERROR: {self.error}"
        return f"<RestoreResult target={self.target!r} {status}>"


class RestoreManager:
    """Gestiona la restauración de diferentes tipos de copias de seguridad."""

    # ------------------------------------------------------------------
    # SQLite
    # ------------------------------------------------------------------
    def restore_sqlite(self, backup_path: Path, target_db_path: Path) -> RestoreResult:
        """
        Restaura un backup SQLite sobre el archivo de BD destino.

        Args:
            backup_path:    Ruta al archivo de backup (.db o .zip).
            target_db_path: Ruta donde se restaurará la BD.
        """
        db_file = self._extract_if_compressed(backup_path, suffix=".db")
        if db_file is None:
            return RestoreResult(
                False, str(target_db_path), "No se pudo extraer el backup."
            )

        target_db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            src_conn = sqlite3.connect(str(db_file))
            dst_conn = sqlite3.connect(str(target_db_path))
            src_conn.backup(dst_conn)
            src_conn.close()
            dst_conn.close()
            logger.info("SQLite restaurado en: %s", target_db_path)
            return RestoreResult(True, str(target_db_path))
        except sqlite3.Error as exc:
            logger.error("Error al restaurar SQLite: %s", exc)
            return RestoreResult(False, str(target_db_path), str(exc))
        finally:
            # Limpia el archivo temporal extraído si era un zip
            if db_file != backup_path and db_file.exists():
                db_file.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # PostgreSQL
    # ------------------------------------------------------------------
    def restore_postgresql(
        self,
        backup_path: Path,
        host: str = "localhost",
        port: int = 5432,
        database: str = "",
        user: str = "postgres",
        password: str = "",
        create_db: bool = False,
    ) -> RestoreResult:
        """
        Restaura un volcado PostgreSQL usando psql o pg_restore.

        Args:
            backup_path: Ruta al archivo .sql o .dump.
            create_db:   Si True, intenta crear la BD antes de restaurar.
        """
        import os  # noqa: PLC0415

        env = os.environ.copy()
        env["PGPASSWORD"] = password

        target_label = f"PostgreSQL:{host}/{database}"

        if create_db:
            self._pg_create_db(host, port, user, database, env)

        suffix = backup_path.suffix.lower()
        if suffix == ".sql" or suffix == ".gz":
            cmd = [
                "psql",
                "-h",
                host,
                "-p",
                str(port),
                "-U",
                user,
                "-d",
                database,
                "-f",
                str(backup_path),
            ]
            tool = "psql"
        else:
            # formato custom o directory de pg_dump
            cmd = [
                "pg_restore",
                "-h",
                host,
                "-p",
                str(port),
                "-U",
                user,
                "-d",
                database,
                "--clean",
                str(backup_path),
            ]
            tool = "pg_restore"

        return self._run_command(cmd, env, target_label, tool)

    def _pg_create_db(
        self, host: str, port: int, user: str, database: str, env: dict
    ) -> None:
        cmd = [
            "createdb",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            database,
        ]
        subprocess.run(cmd, env=env, capture_output=True, timeout=30)

    # ------------------------------------------------------------------
    # MySQL / MariaDB
    # ------------------------------------------------------------------
    def restore_mysql(
        self,
        backup_path: Path,
        host: str = "localhost",
        port: int = 3306,
        database: str = "",
        user: str = "root",
        password: str = "",
        create_db: bool = False,
    ) -> RestoreResult:
        """Restaura un volcado MySQL/MariaDB."""
        target_label = f"MySQL:{host}/{database}"

        if create_db:
            self._mysql_create_db(host, port, user, password, database)

        cmd = [
            "mysql",
            f"--host={host}",
            f"--port={port}",
            f"--user={user}",
            f"--password={password}",
            database,
        ]
        try:
            with open(backup_path, "r", encoding="utf-8") as fh:
                result = subprocess.run(
                    cmd,
                    stdin=fh,
                    capture_output=True,
                    text=True,
                    timeout=3600,
                )
            if result.returncode != 0:
                logger.error("mysql stderr: %s", result.stderr)
                return RestoreResult(False, target_label, result.stderr)
            logger.info("MySQL restaurado: %s", target_label)
            return RestoreResult(True, target_label)
        except FileNotFoundError:
            return RestoreResult(False, target_label, "mysql client no encontrado.")
        except subprocess.TimeoutExpired:
            return RestoreResult(False, target_label, "Timeout agotado.")

    def _mysql_create_db(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> None:
        cmd = [
            "mysql",
            f"--host={host}",
            f"--port={port}",
            f"--user={user}",
            f"--password={password}",
            "-e",
            f"CREATE DATABASE IF NOT EXISTS `{database}`;",
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)

    # ------------------------------------------------------------------
    # SQL Server
    # ------------------------------------------------------------------
    def restore_sqlserver(
        self,
        backup_path: Path,
        host: str = "localhost",
        port: int = 1433,
        database: str = "",
        user: str = "sa",
        password: str = "",
        server_bak_path: str = "",
    ) -> RestoreResult:
        """
        Restaura una BD SQL Server.

        Si server_bak_path está definido, ejecuta RESTORE DATABASE via sqlcmd.
        En caso contrario aplica el script SQL generado por el fallback pyodbc.
        """
        target_label = f"SQLServer:{host}/{database}"

        if server_bak_path:
            tsql = (
                f"RESTORE DATABASE [{database}] "
                f"FROM DISK = N'{server_bak_path}' "
                "WITH REPLACE, RECOVERY;"
            )
            cmd = [
                "sqlcmd",
                "-S",
                f"{host},{port}",
                "-U",
                user,
                "-P",
                password,
                "-Q",
                tsql,
            ]
            return self._run_command(cmd, None, target_label, "sqlcmd")

        # Fallback: ejecutar el script SQL con sqlcmd
        cmd = [
            "sqlcmd",
            "-S",
            f"{host},{port}",
            "-U",
            user,
            "-P",
            password,
            "-i",
            str(backup_path),
        ]
        return self._run_command(cmd, None, target_label, "sqlcmd")

    # ------------------------------------------------------------------
    # MDB / Access
    # ------------------------------------------------------------------
    def restore_mdb(self, backup_path: Path, target_path: Path) -> RestoreResult:
        """Restaura un archivo MDB copiando el backup al destino."""
        target_label = f"MDB:{target_path}"
        extracted = self._extract_if_compressed(backup_path, suffix=target_path.suffix)
        if extracted is None:
            return RestoreResult(False, target_label, "No se pudo extraer el backup.")
        try:
            shutil.copy2(extracted, target_path)
            logger.info("MDB restaurado en: %s", target_path)
            return RestoreResult(True, target_label)
        except OSError as exc:
            logger.error("Error al restaurar MDB: %s", exc)
            return RestoreResult(False, target_label, str(exc))
        finally:
            if extracted != backup_path and extracted.exists():
                extracted.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Carpeta
    # ------------------------------------------------------------------
    def restore_folder(
        self, backup_path: Path, target_dir: Path, overwrite: bool = True
    ) -> RestoreResult:
        """
        Restaura una carpeta desde un backup comprimido.

        Args:
            backup_path: Ruta al .zip o .tar.gz.
            target_dir:  Directorio destino.
            overwrite:   Si True, elimina el contenido existente primero.
        """
        target_label = f"Folder:{target_dir}"
        if overwrite and target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            suffix = "".join(backup_path.suffixes).lower()
            if suffix.endswith(".zip"):
                with zipfile.ZipFile(backup_path, "r") as zf:
                    zf.extractall(target_dir)
            elif suffix.endswith(".tar.gz") or suffix.endswith(".tgz"):
                with tarfile.open(backup_path, "r:gz") as tf:
                    tf.extractall(target_dir)
            else:
                # Sin compresión: copia el directorio
                if backup_path.is_dir():
                    shutil.copytree(backup_path, target_dir, dirs_exist_ok=True)
                else:
                    shutil.copy2(backup_path, target_dir)

            logger.info("Carpeta restaurada en: %s", target_dir)
            return RestoreResult(True, target_label)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al restaurar carpeta: %s", exc)
            return RestoreResult(False, target_label, str(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_if_compressed(backup_path: Path, suffix: str = "") -> Optional[Path]:
        """
        Si backup_path es .zip, extrae el primer archivo coincidente
        con suffix en un directorio temporal. Devuelve la ruta al archivo.
        """
        if not backup_path.exists():
            logger.error("Backup no encontrado: %s", backup_path)
            return None

        path_suffix = "".join(backup_path.suffixes).lower()
        if path_suffix.endswith(".zip"):
            import tempfile  # noqa: PLC0415

            tmp_dir = Path(tempfile.mkdtemp(prefix="solba_restore_"))
            with zipfile.ZipFile(backup_path, "r") as zf:
                zf.extractall(tmp_dir)
            # Buscar el archivo con el sufijo deseado
            candidates = (
                list(tmp_dir.rglob(f"*{suffix}"))
                if suffix
                else list(tmp_dir.rglob("*"))
            )
            if candidates:
                return candidates[0]
            return None

        if path_suffix.endswith(".tar.gz") or path_suffix.endswith(".tgz"):
            import tempfile  # noqa: PLC0415

            tmp_dir = Path(tempfile.mkdtemp(prefix="solba_restore_"))
            with tarfile.open(backup_path, "r:gz") as tf:
                tf.extractall(tmp_dir)
            candidates = (
                list(tmp_dir.rglob(f"*{suffix}"))
                if suffix
                else list(tmp_dir.rglob("*"))
            )
            if candidates:
                return candidates[0]
            return None

        # El archivo no está comprimido
        return backup_path

    @staticmethod
    def _run_command(
        cmd: list, env: Optional[dict], target_label: str, tool: str
    ) -> RestoreResult:
        """Ejecuta un comando externo y devuelve un RestoreResult."""
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            if result.returncode != 0:
                logger.error("%s stderr: %s", tool, result.stderr)
                return RestoreResult(False, target_label, result.stderr)
            logger.info("%s: restauración completada → %s", tool, target_label)
            return RestoreResult(True, target_label)
        except FileNotFoundError:
            msg = f"{tool} no encontrado en el sistema."
            logger.error(msg)
            return RestoreResult(False, target_label, msg)
        except subprocess.TimeoutExpired:
            msg = "Timeout agotado durante la restauración."
            logger.error(msg)
            return RestoreResult(False, target_label, msg)
