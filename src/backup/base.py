"""Base module for backup providers defining the Template Method pattern."""

import abc
import datetime
import logging
import os
import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class BackupResult:
    """Represents the result of a backup operation.

    Attributes:
        success: Whether the backup was successful.
        destination: The final path of the backup file.
        size_bytes: The size of the backup file in bytes.
        error: An error message if the backup failed, None otherwise.
    """

    success: bool
    destination: str
    size_bytes: int
    error: Optional[str] = None


class BaseBackup(abc.ABC):
    """Abstract base class for all backup providers."""

    def __init__(self, dest_dir: str | Path, compression: str = "none") -> None:
        """Initializes the base backup provider.

        Args:
            dest_dir: The directory where backups will be stored.
            compression: The compression format ('zip', 'tar.gz', or 'none').
        """
        self.dest_dir = Path(dest_dir)
        self.compression = compression.lower()
        self.logger = logging.getLogger(self.__class__.__name__)

        if not self.dest_dir.exists():
            self.dest_dir.mkdir(parents=True, exist_ok=True)

    def execute_backup(self, **kwargs: Any) -> BackupResult:
        """Executes the backup process using the Template Method pattern.

        Args:
            **kwargs: Provider-specific arguments.

        Returns:
            A BackupResult instance containing the outcome of the operation.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            # Step 1: Perform the raw backup
            raw_path = self._do_backup(timestamp, **kwargs)

            # Step 2: Compress the backup if requested
            final_path = self._compress(raw_path)

            # Step 3: Calculate final size
            size = Path(final_path).stat().st_size

            return BackupResult(
                success=True,
                destination=str(final_path),
                size_bytes=size,
            )
        except Exception as e:
            self.logger.exception("Backup failed: %s", e)
            return BackupResult(
                success=False,
                destination="",
                size_bytes=0,
                error=str(e),
            )

    @abc.abstractmethod
    def _do_backup(self, timestamp: str, **kwargs: Any) -> Path:
        """Performs the actual backup operation.

        Args:
            timestamp: The current timestamp string to use in filenames.
            **kwargs: Provider-specific arguments.

        Returns:
            The path to the raw, uncompressed backup file or folder.

        Raises:
            Exception: If the backup operation fails.
        """
        pass

    def _compress(self, raw_path: Path) -> Path:
        """Compresses the raw backup file or directory.

        Args:
            raw_path: The path to the file or directory to compress.

        Returns:
            The path to the final compressed file, or original path if no compression.
        """
        if self.compression == "none":
            return raw_path

        if self.compression == "zip":
            dest_file = raw_path.with_suffix(raw_path.suffix + ".zip")
            with zipfile.ZipFile(dest_file, "w", zipfile.ZIP_DEFLATED) as zf:
                if raw_path.is_dir():
                    for root, _, files in os.walk(raw_path):
                        for file in files:
                            file_path = Path(root) / file
                            arcname = file_path.relative_to(raw_path.parent)
                            zf.write(file_path, arcname)
                else:
                    zf.write(raw_path, raw_path.name)

            self._cleanup_raw(raw_path)
            return dest_file

        if self.compression == "tar.gz":
            dest_file = raw_path.with_suffix(raw_path.suffix + ".tar.gz")
            with tarfile.open(dest_file, "w:gz") as tf:
                tf.add(raw_path, arcname=raw_path.name)

            self._cleanup_raw(raw_path)
            return dest_file

        self.logger.warning("Unsupported compression: %s, skipping.", self.compression)
        return raw_path

    def _cleanup_raw(self, raw_path: Path) -> None:
        """Removes the raw uncompressed backup after compression.

        Args:
            raw_path: The path to the uncompressed backup.
        """
        if raw_path.is_dir():
            shutil.rmtree(raw_path)
        else:
            raw_path.unlink()

    def purge_old_backups(self, prefix: str, retention_days: int) -> int:
        """Deletes backups older than a specified number of days.

        Args:
            prefix: The prefix of the backup files to consider.
            retention_days: The number of days to keep backups.

        Returns:
            The number of files deleted.
        """
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        deleted_count = 0

        for file_path in self.dest_dir.iterdir():
            if file_path.is_file() and file_path.name.startswith(prefix):
                file_mtime = datetime.datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        self.logger.info("Purged old backup: %s", file_path)
                    except OSError as e:
                        self.logger.error("Failed to delete %s: %s", file_path, e)

        return deleted_count
