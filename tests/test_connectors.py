"""
tests/test_connectors.py — Pruebas de conectores de bases de datos.
Todos los conectores se prueban AISLADOS del sistema real (sin BD reales).
"""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.core.models import JobCreate
from src.db.models import Job


# ─── PostgreSQL ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_postgresql_extract_calls_pg_dump(mocker, tmp_path):
    """Verifica que PostgreSQLConnector invoca 'pg_dump' con los parámetros correctos."""
    import subprocess

    from src.connectors.postgresql import PostgreSQLConnector, _windows_subprocess_flags

    job = Job(
        id=1,
        name="PG Test",
        db_type="postgresql",
        db_host="localhost",
        db_port=5432,
        db_name="testdb",
        db_user="user",
        db_password="s3cr3t",
    )
    connector = PostgreSQLConnector()
    output_path = tmp_path / "dump.sql"

    mocker.patch("src.connectors.postgresql._find_pg_dump", return_value="pg_dump")

    def make_popen(*args, **kwargs):
        dump_file = kwargs.get("stdout")
        mock_proc = MagicMock()

        def communicate(timeout=None):
            if dump_file is not None and hasattr(dump_file, "write"):
                dump_file.write(b"-- pg_dump mock output\n")
                if hasattr(dump_file, "flush"):
                    dump_file.flush()
            return (b"", None)

        mock_proc.communicate = communicate
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()
        return mock_proc

    mock_popen = mocker.patch(
        "src.connectors.postgresql.subprocess.Popen", side_effect=make_popen
    )

    async def fake_to_thread(fn, *args, **kwargs):
        fn(*args, **kwargs)

    mocker.patch("asyncio.to_thread", side_effect=fake_to_thread)

    result = await connector.extract(job, output_path)

    assert result is True
    assert output_path.exists() and output_path.stat().st_size > 0
    mock_popen.assert_called_once()
    cmd, popen_kwargs = mock_popen.call_args[0][0], mock_popen.call_args[1]
    assert cmd[0] == "pg_dump"
    assert "-h" in cmd and "localhost" in cmd
    assert "-p" in cmd and "5432" in cmd
    assert "-U" in cmd and "user" in cmd
    assert cmd[cmd.index("-F") + 1] == "p"
    assert "--no-password" in cmd
    assert "testdb" in cmd
    assert popen_kwargs.get("stderr") is subprocess.PIPE
    assert popen_kwargs.get("creationflags") == _windows_subprocess_flags()
    env_arg = popen_kwargs.get("env", {})
    assert env_arg.get("PGPASSWORD") == "s3cr3t"
    assert "s3cr3t" not in " ".join(cmd)


@pytest.mark.asyncio
async def test_postgresql_extract_raises_on_failure(mocker, tmp_path):
    """Verifica que un fallo de pg_dump lanza una excepción."""
    from src.connectors.postgresql import PostgreSQLConnector

    job = Job(
        id=1,
        name="PG Fail",
        db_type="postgresql",
        db_host="localhost",
        db_name="testdb",
        db_user="user",
    )
    connector = PostgreSQLConnector()

    mocker.patch("src.connectors.postgresql._find_pg_dump", return_value="pg_dump")

    def make_popen_fail(*args, **kwargs):
        mock_proc = MagicMock()

        def communicate(timeout=None):
            return (b"Connection refused", None)

        mock_proc.communicate = communicate
        mock_proc.returncode = 1
        mock_proc.kill = MagicMock()
        return mock_proc

    mocker.patch(
        "src.connectors.postgresql.subprocess.Popen", side_effect=make_popen_fail
    )

    async def fake_to_thread(fn, *args, **kwargs):
        fn(*args, **kwargs)

    mocker.patch("asyncio.to_thread", side_effect=fake_to_thread)

    with pytest.raises(Exception) as exc_info:
        await connector.extract(job, tmp_path / "dump.sql")
    assert "pg_dump" in str(exc_info.value).lower() or "Connection" in str(exc_info.value)


@pytest.mark.asyncio
async def test_postgresql_extract_missing_required_fields(tmp_path):
    """Verifica que faltan campos obligatorios lanza ValueError."""
    from src.connectors.postgresql import PostgreSQLConnector

    job = Job(id=1, name="PG Incomplete", db_type="postgresql")  # sin db_name ni db_host
    connector = PostgreSQLConnector()

    with pytest.raises(Exception):
        await connector.extract(job, tmp_path / "dump.sql")


# ─── MySQL ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mysql_extract_calls_mysqldump(mocker, tmp_path):
    """Verifica que MySQLConnector invoca 'mysqldump' con los parámetros correctos."""
    from src.connectors.mysql import MySQLConnector

    job = Job(id=2, name="MySQL Test", db_type="mysql",
              db_host="127.0.0.1", db_name="mysqldb",
              db_user="root", db_password="rootpass")
    connector = MySQLConnector()
    output_path = tmp_path / "dump.sql"

    async def fake_to_thread(fn, *args, **kwargs):
        fn()

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)
    mocker.patch("asyncio.to_thread", side_effect=fake_to_thread)

    result = await connector.extract(job, output_path)
    assert result is True

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "mysqldump"
    assert "mysqldb" in call_args
    # Contraseña NO debe ir en texto plano en la línea de comandos
    assert "rootpass" not in " ".join(call_args)


@pytest.mark.asyncio
async def test_mysql_extract_raises_on_failure(mocker, tmp_path):
    """Verifica que un fallo de mysqldump lanza excepción."""
    from src.connectors.mysql import MySQLConnector
    import subprocess

    job = Job(id=2, name="MySQL Fail", db_type="mysql",
              db_host="127.0.0.1", db_name="mysqldb", db_user="root")
    connector = MySQLConnector()

    def fake_run_fail():
        raise subprocess.CalledProcessError(1, "mysqldump", stderr="Access denied")

    mocker.patch("asyncio.to_thread", side_effect=lambda fn, *a, **k: fake_run_fail() or True)

    with pytest.raises(Exception):
        await connector.extract(job, tmp_path / "dump.sql")


# ─── SQLite ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sqlite_extract_copies_file(mocker, tmp_path):
    """Verifica que SQLiteConnector copia el archivo .db al destino."""
    from src.connectors.sqlite import SQLiteConnector

    # Crear un archivo de BD SQLite real mínimo
    import sqlite3 as _sqlite3
    db_src = tmp_path / "source.db"
    conn = _sqlite3.connect(str(db_src))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    job = Job(id=3, name="SQLite Test", db_type="sqlite", db_name=str(db_src))
    connector = SQLiteConnector()
    output_path = tmp_path / "dump.sqlite"

    result = await connector.extract(job, output_path)
    assert result is True
    assert output_path.exists()
    assert output_path.stat().st_size > 0


# ─── SQL Server ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sqlserver_extract_calls_sqlcmd(mocker, tmp_path):
    """Verifica que SQLServerConnector invoca 'sqlcmd' con los parámetros correctos."""
    from src.connectors.sqlserver import SQLServerConnector

    job = Job(id=4, name="SS Test", db_type="sqlserver",
              db_host="localhost", db_name="mssqldb",
              db_user="sa", db_password="sapass")
    connector = SQLServerConnector()
    output_path = tmp_path / "dump.bak"

    async def fake_to_thread(fn, *args, **kwargs):
        fn()

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)
    mocker.patch("asyncio.to_thread", side_effect=fake_to_thread)

    result = await connector.extract(job, output_path)
    assert result is True

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert call_args[0] in ("sqlcmd", "sqlcmd.exe")
    assert "mssqldb" in " ".join(call_args)
