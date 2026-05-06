"""Tests for backup providers."""

import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.backup.base import BackupResult
from src.backup.folder_backup import FolderBackup
from src.backup.mdb_backup import MDBBackup
from src.backup.postgresql_backup import PostgreSQLBackup
from src.backup.sql_backup import SQLBackup
from src.backup.sqlite_backup import SQLiteBackup


@pytest.fixture
def temp_dest_dir(tmp_path):
    """Fixture to provide a temporary destination directory."""
    return tmp_path / "backups"


def test_base_backup_success(temp_dest_dir):
    """Test the template method execution for a successful backup."""
    source_folder = temp_dest_dir.parent / "source"
    source_folder.mkdir()
    (source_folder / "file.txt").write_text("data")

    backup = FolderBackup(dest_dir=temp_dest_dir, compression="none")
    result = backup.execute_backup(folder_path=source_folder)

    assert isinstance(result, BackupResult)
    assert result.success is True
    assert result.error is None
    assert "source_" in result.destination


def test_base_backup_compression_zip(temp_dest_dir):
    """Test zip compression in the base class."""
    source_folder = temp_dest_dir.parent / "source"
    source_folder.mkdir()
    (source_folder / "file.txt").write_text("data")

    backup = FolderBackup(dest_dir=temp_dest_dir, compression="zip")
    result = backup.execute_backup(folder_path=source_folder)

    assert result.success is True
    assert result.destination.endswith(".zip")
    assert Path(result.destination).exists()


def test_base_backup_compression_targz(temp_dest_dir):
    """Test tar.gz compression in the base class."""
    source_folder = temp_dest_dir.parent / "source"
    source_folder.mkdir()
    (source_folder / "file.txt").write_text("data")

    backup = FolderBackup(dest_dir=temp_dest_dir, compression="tar.gz")
    result = backup.execute_backup(folder_path=source_folder)

    assert result.success is True
    assert result.destination.endswith(".tar.gz")
    assert Path(result.destination).exists()


def test_purge_old_backups(temp_dest_dir):
    """Test purging of old backups."""
    backup = FolderBackup(dest_dir=temp_dest_dir)
    temp_dest_dir.mkdir(exist_ok=True)

    # Create an old file
    old_file = temp_dest_dir / "test_old.bak"
    old_file.write_text("old")
    # Set mtime to 10 days ago
    past_time = (datetime.datetime.now() - datetime.timedelta(days=10)).timestamp()
    import os

    os.utime(old_file, (past_time, past_time))

    # Create a new file
    new_file = temp_dest_dir / "test_new.bak"
    new_file.write_text("new")

    deleted = backup.purge_old_backups("test", retention_days=5)

    assert deleted == 1
    assert not old_file.exists()
    assert new_file.exists()


def test_sqlite_backup(temp_dest_dir, mocker):
    """Test SQLite backup execution."""
    mock_connect = mocker.patch("sqlite3.connect")
    mocker.patch("pathlib.Path.stat", return_value=mocker.Mock(st_size=1024))

    db_file = temp_dest_dir.parent / "test.db"
    db_file.write_text("dummy")

    backup = SQLiteBackup(dest_dir=temp_dest_dir)
    result = backup.execute_backup(db_path=db_file)

    assert result.success is True
    assert mock_connect.call_count == 2


def test_postgresql_backup(temp_dest_dir, mocker):
    """Test PostgreSQL backup execution."""
    mock_run = mocker.patch("subprocess.run")
    mocker.patch("pathlib.Path.stat", return_value=mocker.Mock(st_size=1024))

    backup = PostgreSQLBackup(dest_dir=temp_dest_dir)
    result = backup.execute_backup(dbname="testdb", user="user", password="pwd")

    assert result.success is True
    mock_run.assert_called_once()
    assert "pg_dump" in mock_run.call_args[0][0]


def test_sql_backup_mysql(temp_dest_dir, mocker):
    """Test MySQL backup execution."""
    mock_pymysql = MagicMock()
    mocker.patch.dict("sys.modules", {"pymysql": mock_pymysql})

    mock_conn = MagicMock()
    mock_pymysql.connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mocking SHOW TABLES and SELECT
    mock_cursor.fetchall.side_effect = [[("table1",)], [("val1",)]]
    mock_cursor.fetchone.return_value = ["table1", "CREATE TABLE table1 (...)"]

    backup = SQLBackup(dest_dir=temp_dest_dir)
    result = backup.execute_backup(db_type="mysql", dbname="testdb")

    assert result.success is True
    mock_pymysql.connect.assert_called_once()
    assert Path(result.destination).exists()

    content = Path(result.destination).read_text(encoding="utf-8")
    assert "CREATE TABLE table1 (...)" in content


def test_sql_backup_sqlserver(temp_dest_dir, mocker):
    """Test SQL Server backup execution."""
    mock_pyodbc = MagicMock()
    mocker.patch.dict("sys.modules", {"pyodbc": mock_pyodbc})
    mocker.patch("pathlib.Path.stat", return_value=mocker.Mock(st_size=1024))

    mock_conn = MagicMock()
    mock_pyodbc.connect.return_value.__enter__.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.nextset.return_value = False

    backup = SQLBackup(dest_dir=temp_dest_dir)
    result = backup.execute_backup(db_type="sqlserver", dbname="testdb")

    assert result.success is True
    mock_pyodbc.connect.assert_called_once()
    mock_cursor.execute.assert_called_once()
    assert "BACKUP DATABASE [testdb]" in mock_cursor.execute.call_args[0][0]


def test_mdb_backup(temp_dest_dir, mocker):
    """Test MDB backup execution."""
    mock_copy = mocker.patch("shutil.copy2")
    mocker.patch("pathlib.Path.stat", return_value=mocker.Mock(st_size=1024))

    db_file = temp_dest_dir.parent / "test.mdb"
    db_file.write_text("dummy")

    backup = MDBBackup(dest_dir=temp_dest_dir)
    result = backup.execute_backup(db_path=db_file)

    assert result.success is True
    mock_copy.assert_called_once()
