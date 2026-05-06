"""SQLite backup provider module."""

import sqlite3
from pathlib import Path
from typing import Any

from .base import BaseBackup


class SQLiteBackup(BaseBackup):
    """Backup provider for SQLite databases."""

    def _do_backup(self, timestamp: str, **kwargs: Any) -> Path:
        """Performs a backup of an SQLite database.

        Args:
            timestamp: The current timestamp string to use in filenames.
            **kwargs: Must contain 'db_path' (str or Path), the path to the database.

        Returns:
            The path to the created backup file.

        Raises:
            ValueError: If 'db_path' is not provided or file does not exist.
        """
        db_path = kwargs.get("db_path")
        if not db_path:
            raise ValueError("db_path is required for SQLite backup.")

        source_path = Path(db_path)
        if not source_path.exists():
            raise ValueError(f"Database file not found: {source_path}")

        db_name = source_path.stem
        dest_filename = f"{db_name}_{timestamp}.db"
        dest_path = self.dest_dir / dest_filename

        with sqlite3.connect(source_path) as src_conn:
            with sqlite3.connect(dest_path) as dest_conn:
                src_conn.backup(dest_conn)

        return dest_path
