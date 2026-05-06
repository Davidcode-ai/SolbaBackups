"""
Tests del detector de bases de datos.
"""

import socket
from unittest.mock import MagicMock, patch

from src.detector.db_detector import (
    DatabaseDetector,
    DB_PORTS,
    SQLITE_EXTENSIONS,
    MDB_EXTENSIONS,
)


class TestDatabaseDetectorPorts:
    def test_known_ports_defined(self):
        assert "MySQL/MariaDB" in DB_PORTS
        assert "PostgreSQL" in DB_PORTS
        assert "SQL Server" in DB_PORTS
        assert DB_PORTS["PostgreSQL"] == 5432

    def test_sqlite_extensions(self):
        assert ".db" in SQLITE_EXTENSIONS
        assert ".sqlite" in SQLITE_EXTENSIONS
        assert ".sqlite3" in SQLITE_EXTENSIONS

    def test_mdb_extensions(self):
        assert ".mdb" in MDB_EXTENSIONS
        assert ".accdb" in MDB_EXTENSIONS


class TestCheckPort:
    def test_open_port(self):
        detector = DatabaseDetector(timeout=1.0)
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=None)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            result = detector._check_port("127.0.0.1", 5432)
        assert result is True

    def test_closed_port(self):
        detector = DatabaseDetector(timeout=0.1)
        with patch("socket.create_connection", side_effect=ConnectionRefusedError):
            result = detector._check_port("127.0.0.1", 9999)
        assert result is False

    def test_timeout_port(self):
        detector = DatabaseDetector(timeout=0.1)
        with patch("socket.create_connection", side_effect=socket.timeout):
            result = detector._check_port("192.0.2.1", 5432)
        assert result is False


class TestDetectNetwork:
    def test_returns_open_services(self):
        detector = DatabaseDetector(timeout=0.1)

        def mock_check(host, port):
            return port == 5432  # Solo PostgreSQL "abierto"

        with patch.object(detector, "_check_port", side_effect=mock_check):
            results = detector.detect_network(host="127.0.0.1")

        assert len(results) == 1
        assert results[0]["db"] == "PostgreSQL"
        assert results[0]["port"] == "5432"
        assert results[0]["status"] == "OPEN"

    def test_no_services_found(self):
        detector = DatabaseDetector(timeout=0.1)
        with patch.object(detector, "_check_port", return_value=False):
            results = detector.detect_network(host="192.0.2.0")
        assert results == []

    def test_custom_ports(self):
        detector = DatabaseDetector(timeout=0.1)

        def mock_check(host, port):
            return port == 9999

        with patch.object(detector, "_check_port", side_effect=mock_check):
            results = detector.detect_network(
                host="127.0.0.1",
                custom_ports={"CustomDB": 9999},
            )

        assert any(r["db"] == "CustomDB" for r in results)


class TestDetectLocalFiles:
    def test_finds_sqlite_files(self, tmp_path):
        # Crear archivos SQLite y MDB de prueba
        (tmp_path / "data.db").write_text("SQLite file")
        (tmp_path / "archive.sqlite3").write_text("SQLite file")
        (tmp_path / "database.mdb").write_bytes(b"\x00\x01")
        (tmp_path / "document.txt").write_text("not a DB")

        detector = DatabaseDetector()
        results = detector.detect_local_files(search_dirs=[str(tmp_path)], max_depth=1)

        db_types = [r["db"] for r in results]
        assert "SQLite" in db_types
        assert "MDB/Access" in db_types
        assert not any(r["db"] == "TXT" for r in results)

    def test_empty_directory(self, tmp_path):
        detector = DatabaseDetector()
        results = detector.detect_local_files(search_dirs=[str(tmp_path)], max_depth=1)
        assert results == []

    def test_nonexistent_directory(self):
        detector = DatabaseDetector()
        results = detector.detect_local_files(
            search_dirs=["/nonexistent/path/xyz"], max_depth=1
        )
        assert results == []

    def test_max_depth_limits_search(self, tmp_path):
        # Crear archivo profundo
        deep_dir = tmp_path / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep.db").write_text("deep")

        detector = DatabaseDetector()
        results = detector.detect_local_files(search_dirs=[str(tmp_path)], max_depth=2)
        # No debería encontrar el archivo a profundidad 4
        paths = [r["path"] for r in results]
        assert not any("deep.db" in p for p in paths)
