"""Microsoft Access (MDB/ACCDB) backup provider module."""

import shutil
from pathlib import Path
from typing import Any

from .base import BaseBackup


class MDBBackup(BaseBackup):
    """Backup provider for Microsoft Access databases (.mdb or .accdb)."""

    def _do_backup(self, timestamp: str, **kwargs: Any) -> Path:
        """Performs a backup of an MDB/ACCDB file by copying it.

        Args:
            timestamp: The current timestamp string to use in filenames.
            **kwargs: Must contain 'db_path', the path to the database file.

        Returns:
            The path to the created backup file.

        Raises:
            ValueError: If 'db_path' is missing or does not exist.
        """
        db_path = kwargs.get("db_path")
        if not db_path:
            raise ValueError("db_path is required for MDB backup.")

        source_path = Path(db_path)
        if not source_path.exists():
            raise ValueError(f"Database file not found: {source_path}")

        db_name = source_path.stem
        ext = source_path.suffix
        dest_filename = f"{db_name}_{timestamp}{ext}"
        dest_path = self.dest_dir / dest_filename

        shutil.copy2(source_path, dest_path)

        return dest_path
