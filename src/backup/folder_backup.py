"""Folder backup provider module."""

import shutil
from pathlib import Path
from typing import Any

from .base import BaseBackup


class FolderBackup(BaseBackup):
    """Backup provider for regular folders/directories."""

    def _do_backup(self, timestamp: str, **kwargs: Any) -> Path:
        """Performs a backup of a folder by copying it.

        Args:
            timestamp: The current timestamp string to use in filenames.
            **kwargs: Must contain 'folder_path', the path to the folder.

        Returns:
            The path to the created backup folder.

        Raises:
            ValueError: If 'folder_path' is missing or does not exist.
        """
        folder_path = kwargs.get("folder_path")
        if not folder_path:
            raise ValueError("folder_path is required for Folder backup.")

        source_path = Path(folder_path)
        if not source_path.exists() or not source_path.is_dir():
            raise ValueError(f"Directory not found: {source_path}")

        folder_name = source_path.name
        dest_dirname = f"{folder_name}_{timestamp}"
        dest_path = self.dest_dir / dest_dirname

        shutil.copytree(source_path, dest_path)

        return dest_path
