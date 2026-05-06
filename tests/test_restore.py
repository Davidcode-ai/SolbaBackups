"""
Tests del módulo de restauración.
"""

import sqlite3
import zipfile
from pathlib import Path

import pytest

from src.restore.restore_manager import RestoreManager, RestoreResult


@pytest.fixture()
def sample_sqlite_backup(tmp_path) -> Path:
    """Crea un backup SQLite de prueba."""
    db_file = tmp_path / "backup_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE items (id INTEGER, value TEXT)")
    conn.execute("INSERT INTO items VALUES (1, 'restored_item')")
    conn.commit()
    conn.close()
    return db_file


@pytest.fixture()
def zipped_sqlite_backup(tmp_path, sample_sqlite_backup) -> Path:
    """Empaqueta el backup SQLite en un ZIP."""
    zip_path = tmp_path / "backup_test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(sample_sqlite_backup, sample_sqlite_backup.name)
    return zip_path


@pytest.fixture()
def sample_folder_zip(tmp_path) -> Path:
    """Crea un ZIP con varios archivos de prueba."""
    zip_path = tmp_path / "folder_backup.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("file1.txt", "Contenido 1")
        zf.writestr("subdir/file2.txt", "Contenido 2")
    return zip_path


class TestRestoreResult:
    def test_success(self):
        r = RestoreResult(success=True, target="test")
        assert r.success is True
        assert r.error is None

    def test_failure(self):
        r = RestoreResult(success=False, target="test", error="oops")
        assert r.success is False
        assert r.error == "oops"


class TestRestoreSQLite:
    def test_restore_from_raw_db(self, tmp_path, sample_sqlite_backup):
        rm = RestoreManager()
        target = tmp_path / "restored.db"
        result = rm.restore_sqlite(sample_sqlite_backup, target)

        assert result.success, f"Error: {result.error}"
        assert target.exists()

        conn = sqlite3.connect(str(target))
        rows = conn.execute("SELECT * FROM items").fetchall()
        conn.close()
        assert rows == [(1, "restored_item")]

    def test_restore_from_zip(self, tmp_path, zipped_sqlite_backup):
        rm = RestoreManager()
        target = tmp_path / "from_zip.db"
        result = rm.restore_sqlite(zipped_sqlite_backup, target)

        assert result.success, f"Error: {result.error}"
        assert target.exists()

    def test_restore_nonexistent_backup(self, tmp_path):
        rm = RestoreManager()
        result = rm.restore_sqlite(
            Path("/nonexistent/backup.db"),
            tmp_path / "target.db",
        )
        assert not result.success


class TestRestoreFolder:
    def test_restore_from_zip(self, tmp_path, sample_folder_zip):
        rm = RestoreManager()
        target_dir = tmp_path / "restored_folder"
        result = rm.restore_folder(sample_folder_zip, target_dir)

        assert result.success, f"Error: {result.error}"
        assert (target_dir / "file1.txt").exists()
        assert (target_dir / "subdir" / "file2.txt").exists()
        assert (target_dir / "file1.txt").read_text() == "Contenido 1"

    def test_restore_overwrites_existing(self, tmp_path, sample_folder_zip):
        target_dir = tmp_path / "existing"
        target_dir.mkdir()
        (target_dir / "old_file.txt").write_text("old content")

        rm = RestoreManager()
        result = rm.restore_folder(sample_folder_zip, target_dir, overwrite=True)

        assert result.success
        # El archivo viejo no debe existir
        assert not (target_dir / "old_file.txt").exists()

    def test_restore_no_overwrite(self, tmp_path, sample_folder_zip):
        target_dir = tmp_path / "keep_existing"
        target_dir.mkdir()
        (target_dir / "existing.txt").write_text("keep me")

        rm = RestoreManager()
        result = rm.restore_folder(sample_folder_zip, target_dir, overwrite=False)

        assert result.success
        # El archivo existente debe mantenerse
        assert (target_dir / "existing.txt").exists()

    def test_restore_from_directory(self, tmp_path):
        src_dir = tmp_path / "src_backup"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("A")
        (src_dir / "b.txt").write_text("B")

        target_dir = tmp_path / "target"
        rm = RestoreManager()
        result = rm.restore_folder(src_dir, target_dir)

        assert result.success
        assert (target_dir / "a.txt").exists()

    def test_restore_nonexistent_backup(self, tmp_path):
        rm = RestoreManager()
        result = rm.restore_folder(
            Path("/nonexistent/backup.zip"),
            tmp_path / "target",
        )
        assert not result.success


class TestRestoreMDB:
    def test_restore_mdb_file(self, tmp_path):
        # Simular un archivo MDB
        backup = tmp_path / "backup.mdb"
        backup.write_bytes(b"MDB_DATA_HERE")

        target = tmp_path / "restored.mdb"
        rm = RestoreManager()
        result = rm.restore_mdb(backup, target)

        assert result.success
        assert target.exists()
        assert target.read_bytes() == b"MDB_DATA_HERE"

    def test_restore_mdb_nonexistent(self, tmp_path):
        rm = RestoreManager()
        result = rm.restore_mdb(
            Path("/nonexistent/backup.mdb"),
            tmp_path / "target.mdb",
        )
        assert not result.success
