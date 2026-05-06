"""PostgreSQL backup provider module."""

import os
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseBackup


class PostgreSQLBackup(BaseBackup):
    """Backup provider for PostgreSQL databases using pg_dump."""

    def _do_backup(self, timestamp: str, **kwargs: Any) -> Path:
        """Performs a backup of a PostgreSQL database using pg_dump.

        Args:
            timestamp: The current timestamp string to use in filenames.
            **kwargs: Must contain connection parameters
                (dbname, user, host, port, password).

        Returns:
            The path to the created backup file.

        Raises:
            ValueError: If required connection parameters are missing.
            subprocess.CalledProcessError: If pg_dump fails.
        """
        dbname = kwargs.get("dbname")
        if not dbname:
            raise ValueError("dbname is required for PostgreSQL backup.")

        user = kwargs.get("user", "postgres")
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", "5432")
        password = kwargs.get("password", "")

        dest_filename = f"{dbname}_{timestamp}.sql"
        dest_path = self.dest_dir / dest_filename

        env = None
        if password:
            env = os.environ.copy()
            env["PGPASSWORD"] = password

        command = [
            "pg_dump",
            "-h",
            str(host),
            "-p",
            str(port),
            "-U",
            str(user),
            "-f",
            str(dest_path),
            str(dbname),
        ]

        subprocess.run(command, env=env, check=True, capture_output=True)

        return dest_path
