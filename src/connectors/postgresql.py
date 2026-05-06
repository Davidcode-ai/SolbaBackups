"""
src/connectors/postgresql.py — Conector para PostgreSQL.

Implementa ``BaseConnector`` para bases de datos PostgreSQL usando la
herramienta ``pg_dump`` para generar el archivo de backup.

Estrategia de dump:
    Usa ``pg_dump`` con formato ``--format=custom`` (binario comprimido)
    o ``--format=plain`` (SQL texto plano), configurable via ``extra_params``.
    Por defecto se usa ``--format=plain`` para máxima compatibilidad.

Autenticación:
    La contraseña se pasa a ``pg_dump`` via la variable de entorno
    ``PGPASSWORD`` para evitar prompts interactivos y no exponerla
    en la línea de comandos (visible en ``ps aux``).

Localización de pg_dump:
    Se busca en el orden siguiente:
        1. Ruta configurada en ``AppSettings`` (``pg_dump_path``).
        2. Variable de entorno ``PG_DUMP_PATH``.
        3. PATH del sistema.

Requisitos:
    - PostgreSQL client tools instalados en el sistema.
    - Usuario con permisos de SELECT en todas las tablas a respaldar.

Dependencias Python:
    - ``psycopg2-binary`` para ``test_connection()``.
"""

import logging
import os
from pathlib import Path

import psycopg2

from src.connectors.base import BaseConnector

log = logging.getLogger(__name__)

# Nombre del ejecutable de dump en Windows y Linux
PG_DUMP_BINARY = "pg_dump.exe" if os.name == "nt" else "pg_dump"


class PostgreSQLConnector(BaseConnector):
    """
    Conector para bases de datos PostgreSQL.

    Soporta autenticación por usuario/contraseña y conexión SSL.
    Puede respaldar una BD completa o un esquema específico.

    Extra params reconocidos (via ``extra_params``):
        - ``dump_format``: 'plain' (defecto) | 'custom' | 'directory' | 'tar'.
        - ``schema``:      Esquema específico a respaldar (por defecto, todos).
        - ``ssl_mode``:    'disable' | 'require' | 'verify-full'.
        - ``pg_dump_path``: Ruta absoluta al ejecutable ``pg_dump``.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "",
        user: str = "postgres",
        password: str | None = None,
        extra_params: dict | None = None,
    ) -> None:
        """
        Inicializa el conector con los parámetros de conexión de PostgreSQL.

        Args:
            host:         Host del servidor PostgreSQL.
            port:         Puerto (por defecto 5432).
            database:     Nombre de la base de datos a respaldar.
            user:         Usuario de conexión.
            password:     Contraseña en texto claro.
            extra_params: Parámetros adicionales (ver clase docstring).
        """
        pass

    def test_connection(self) -> bool:
        """
        Verifica la conexión a PostgreSQL usando psycopg2.

        Intenta conectar y ejecutar ``SELECT 1`` para validar credenciales
        y disponibilidad del servidor.

        Returns:
            bool: ``True`` si la conexión es válida.
        """
        pass

    def dump(self, output_path: Path) -> Path:
        """
        Ejecuta ``pg_dump`` para generar el backup de la BD.

        Construye el comando con todos los parámetros necesarios,
        inyecta ``PGPASSWORD`` en el entorno del subproceso y
        llama a ``_run_subprocess``.

        Args:
            output_path: Ruta donde guardar el archivo ``.sql`` o ``.dump``.

        Returns:
            Path: Ruta al archivo generado.

        Raises:
            FileNotFoundError: Si ``pg_dump`` no está en el PATH.
            RuntimeError: Si ``pg_dump`` termina con código de error.
        """
        pass

    def get_dump_filename(self) -> str:
        """
        Devuelve el nombre de archivo sugerido para el dump de PostgreSQL.

        Formato: ``{database}_{YYYYMMDD_HHMMSS}.sql``

        Returns:
            str: Nombre de archivo con timestamp UTC.
        """
        pass

    def _build_pg_dump_cmd(self, output_path: Path) -> list[str]:
        """
        Construye la lista de argumentos para el comando ``pg_dump``.

        Incluye: ruta del ejecutable, host, puerto, usuario, nombre de BD,
        formato de salida y ruta de salida. No incluye la contraseña
        (se pasa via ``PGPASSWORD``).

        Args:
            output_path: Ruta de salida para el archivo de dump.

        Returns:
            list[str]: Comando completo listo para pasar a ``subprocess.run``.
        """
        pass

    def _get_pg_dump_binary(self) -> str:
        """
        Resuelve la ruta al ejecutable ``pg_dump``.

        Busca en ``extra_params['pg_dump_path']``, luego en la variable
        de entorno ``PG_DUMP_PATH``, y finalmente confía en el PATH del sistema.

        Returns:
            str: Ruta o nombre del ejecutable de pg_dump.
        """
        pass
