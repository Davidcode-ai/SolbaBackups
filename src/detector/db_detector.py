"""
Detector de bases de datos activas en una máquina/IP.

Estrategias:
  1. Sondeo de puertos TCP conocidos (rápido, sin dependencias extra).
  2. Escaneo nmap (más fiable, requiere nmap instalado en el sistema).

Bases de datos detectadas:
  - MySQL / MariaDB   → puerto 3306
  - PostgreSQL        → puerto 5432
  - SQL Server        → puerto 1433
  - Oracle            → puerto 1521
  - MongoDB           → puerto 27017
  - Redis             → puerto 6379
  - SQLite            → detección de archivos locales
"""

from __future__ import annotations

import logging
import socket
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Puertos por defecto de cada motor de BD
DB_PORTS: Dict[str, int] = {
    "MySQL/MariaDB": 3306,
    "PostgreSQL": 5432,
    "SQL Server": 1433,
    "Oracle": 1521,
    "MongoDB": 27017,
    "Redis": 6379,
    "CouchDB": 5984,
    "Cassandra": 9042,
    "Elasticsearch": 9200,
}

# Extensiones de archivo asociadas a BD basadas en archivos
SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3", ".db3"}
MDB_EXTENSIONS = {".mdb", ".accdb"}


class DatabaseDetector:
    """Detecta bases de datos activas en un host o en el sistema de archivos."""

    def __init__(self, timeout: float = 1.0) -> None:
        """
        Args:
            timeout: Tiempo máximo de espera por puerto (segundos).
        """
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Detección de red
    # ------------------------------------------------------------------
    def detect_network(
        self,
        host: str = "127.0.0.1",
        custom_ports: Optional[Dict[str, int]] = None,
        use_nmap: bool = False,
    ) -> List[Dict[str, str]]:
        """
        Sondea los puertos conocidos en el host especificado.

        Args:
            host:         IP o nombre de host.
            custom_ports: Puertos adicionales a comprobar {nombre: puerto}.
            use_nmap:     Si True, usa python-nmap para un análisis más detallado.

        Returns:
            Lista de dicts con 'db', 'host', 'port', 'status'.
        """
        ports = dict(DB_PORTS)
        if custom_ports:
            ports.update(custom_ports)

        if use_nmap:
            return self._detect_nmap(host, ports)
        return self._detect_sockets(host, ports)

    def _detect_sockets(self, host: str, ports: Dict[str, int]) -> List[Dict[str, str]]:
        """Sondeo TCP simple por sockets."""
        results = []
        for db_name, port in ports.items():
            status = self._check_port(host, port)
            if status:
                results.append(
                    {
                        "db": db_name,
                        "host": host,
                        "port": str(port),
                        "status": "OPEN",
                        "method": "tcp",
                    }
                )
                logger.info("Puerto abierto: %s en %s:%d", db_name, host, port)
            else:
                logger.debug("Puerto cerrado: %s en %s:%d", db_name, host, port)
        return results

    def _detect_nmap(self, host: str, ports: Dict[str, int]) -> List[Dict[str, str]]:
        """Análisis mediante nmap (requiere python-nmap e nmap instalados)."""
        try:
            import nmap  # noqa: PLC0415
        except ImportError:
            logger.warning("python-nmap no instalado. Usando sockets.")
            return self._detect_sockets(host, ports)

        port_list = ",".join(str(p) for p in ports.values())
        nm = nmap.PortScanner()
        try:
            nm.scan(hosts=host, ports=port_list, arguments="-sV --open")
        except nmap.PortScannerError as exc:
            logger.error("Error nmap: %s", exc)
            return self._detect_sockets(host, ports)

        results = []
        port_to_db = {v: k for k, v in ports.items()}

        for scanned_host in nm.all_hosts():
            for proto in nm[scanned_host].all_protocols():
                for port, state_info in nm[scanned_host][proto].items():
                    if state_info["state"] == "open":
                        db_name = port_to_db.get(port, f"Desconocido:{port}")
                        product = state_info.get("product", "")
                        version = state_info.get("version", "")
                        results.append(
                            {
                                "db": db_name,
                                "host": scanned_host,
                                "port": str(port),
                                "status": "OPEN",
                                "product": product,
                                "version": version,
                                "method": "nmap",
                            }
                        )
        return results

    def _check_port(self, host: str, port: int) -> bool:
        """Devuelve True si el puerto TCP está abierto."""
        try:
            with socket.create_connection((host, port), timeout=self.timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    # ------------------------------------------------------------------
    # Detección de archivos locales (SQLite, MDB)
    # ------------------------------------------------------------------
    def detect_local_files(
        self,
        search_dirs: Optional[List[str]] = None,
        max_depth: int = 5,
    ) -> List[Dict[str, str]]:
        """
        Busca archivos de BD (SQLite, MDB) en los directorios indicados.

        Args:
            search_dirs: Lista de rutas a buscar. Por defecto home del usuario.
            max_depth:   Profundidad máxima de búsqueda.

        Returns:
            Lista de dicts con 'db', 'path', 'size_bytes'.
        """
        if search_dirs is None:
            search_dirs = [str(Path.home())]

        results = []
        for base_dir in search_dirs:
            base = Path(base_dir)
            if not base.exists():
                continue
            for file in self._walk_limited(base, max_depth):
                ext = file.suffix.lower()
                if ext in SQLITE_EXTENSIONS:
                    results.append(
                        {
                            "db": "SQLite",
                            "path": str(file),
                            "size_bytes": str(file.stat().st_size),
                        }
                    )
                elif ext in MDB_EXTENSIONS:
                    results.append(
                        {
                            "db": "MDB/Access",
                            "path": str(file),
                            "size_bytes": str(file.stat().st_size),
                        }
                    )
        return results

    @staticmethod
    def _walk_limited(base: Path, max_depth: int):
        """Generador que itera archivos hasta max_depth niveles."""
        for dirpath, dirnames, filenames in os.walk(base):
            current_depth = dirpath.count(os.sep) - str(base).count(os.sep)
            if current_depth >= max_depth:
                dirnames.clear()
                continue
            for fname in filenames:
                yield Path(dirpath) / fname
