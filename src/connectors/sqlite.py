"""
src/connectors/sqlite.py — Conector para SQLite.

Implementa ``BaseConnector`` para bases de datos SQLite locales.

Estrategia de dump:
    SQLite no usa un servidor ni herramientas externas. Se usan dos enfoques:

    Modo 1 — Copia segura (defecto):
        Usa la API ``sqlite3.Connection.backup()`` de Python para hacer una
        copia online de la BD mientras puede estar en uso por otros procesos.
        Este método es safe para BD activas y no requiere cerrar la conexión.

    Modo 2 — Dump SQL:
        Usa ``sqlite3.Connection.iterdump()`` para generar un script SQL
        completo (CREATE TABLE + INSERT INTO), compatible con cualquier
        motor SQL para restauración manual.

    El modo se configura via ``extra_params['dump_mode']``:
        'copy' (defecto) | 'sql'

Caso especial:
    Si la BD SQLite es la propia ``solba_data.db`` de la aplicación,
    se usa siempre el modo 'copy' (backup online) para no bloquear la app.

Requisitos:
    - Ninguna dependencia externa. Usa solo la librería estándar de Python.
    - El usuario del proceso debe tener permisos de lectura sobre el archivo.

Parámetros de conexión específicos:
    - ``database``: Ruta absoluta al archivo ``.db`` de SQLite.
    - ``host``, ``port``, ``user``, ``password``: Se ignoran.
"""

import logging
import shutil
import sqlite3
from pathlib import Path

from src.connectors.base import BaseConnector

log = logging.getLogger(__name__)


class SQLiteConnector(BaseConnector):
    """
    Conector para bases de datos SQLite locales.

    No requiere servidor, usuario ni contraseña. Solo necesita la ruta
    al archivo ``.db`` (pasada como parámetro ``database``).
    """

    def __init__(
        self,
        database: str = "",
        extra_params: dict | None = None,
        # Los siguientes se aceptan pero se ignoran (firma compatible con BaseConnector)
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        """
        Inicializa el conector SQLite.

        Args:
            database:     Ruta absoluta o relativa al archivo ``.db`` de SQLite.
            extra_params: Parámetros opcionales. Se reconoce ``dump_mode``:
                          'copy' (defecto) | 'sql'.
            host:         Ignorado (solo por compatibilidad de firma).
            port:         Ignorado.
            user:         Ignorado.
            password:     Ignorado.
        """
        pass

    def test_connection(self) -> bool:
        """
        Verifica que el archivo SQLite existe y es una BD válida.

        Intenta abrirlo con ``sqlite3.connect`` y ejecutar ``PRAGMA integrity_check``.

        Returns:
            bool: ``True`` si el archivo es una BD SQLite válida y accesible.
        """
        pass

    def dump(self, output_path: Path) -> Path:
        """
        Genera el backup de la BD SQLite según el modo configurado.

        En modo 'copy': usa ``sqlite3.Connection.backup()`` para una copia
        online segura. En modo 'sql': usa ``iterdump()`` para generar SQL.

        Args:
            output_path: Ruta donde guardar la copia (``.db``) o el script (``.sql``).

        Returns:
            Path: Ruta al archivo generado.

        Raises:
            FileNotFoundError: Si el archivo de BD no existe.
            sqlite3.DatabaseError: Si el archivo no es una BD SQLite válida.
        """
        pass

    def get_dump_filename(self) -> str:
        """
        Devuelve el nombre sugerido para el backup.

        Formato: ``{db_stem}_{YYYYMMDD_HHMMSS}.db`` (modo copy)
                 ``{db_stem}_{YYYYMMDD_HHMMSS}.sql`` (modo sql)
        """
        pass

    def _dump_copy(self, output_path: Path) -> Path:
        """
        Hace una copia online de la BD usando ``sqlite3.Connection.backup()``.

        Este método es seguro incluso si la BD está siendo usada por otro
        proceso. SQLite garantiza consistencia a nivel de página.

        Args:
            output_path: Ruta del archivo de destino ``.db``.

        Returns:
            Path: Ruta al archivo de copia creado.
        """
        pass

    def _dump_sql(self, output_path: Path) -> Path:
        """
        Genera un script SQL completo de la BD usando ``iterdump()``.

        El output es un archivo ``.sql`` con sentencias CREATE TABLE e INSERT
        compatible con SQLite y legible por otros motores SQL (con ajustes).

        Args:
            output_path: Ruta del archivo SQL de destino.

        Returns:
            Path: Ruta al archivo SQL generado.
        """
        pass
