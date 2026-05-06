"""
src/connectors/sqlserver.py — Conector para Microsoft SQL Server.

Implementa ``BaseConnector`` para SQL Server usando dos enfoques
complementarios para el dump:

Modo 1 — sqlcmd (script SQL):
    Genera un script SQL de creación de tablas + datos usando queries T-SQL.
    Compatible con todas las versiones de SQL Server.
    Limitación: no incluye objetos especiales (XML, FileStream, etc.).

Modo 2 — BCP (Bulk Copy Program):
    Usa el utilitario ``bcp`` de SQL Server para exportar datos en formato
    nativo binario. Más rápido para tablas grandes pero menos portable.

Por defecto se usa Modo 1 (sqlcmd) por su mayor compatibilidad.

Autenticación:
    Soporta tanto autenticación SQL Server (usuario/contraseña) como
    autenticación Windows integrada (``trusted_connection=yes``).

Requisitos:
    - SQL Server Command Line Tools (``sqlcmd``, ``bcp``) instalados.
    - En Windows: disponible via «Microsoft ODBC Driver for SQL Server».
    - Permisos: VIEW DATABASE STATE, SELECT en todas las tablas.

Dependencias Python:
    - ``pyodbc`` para ``test_connection()``.

Extra params reconocidos:
    - ``sqlcmd_path``:        Ruta al ejecutable ``sqlcmd``.
    - ``trusted_connection``: bool, usa autenticación Windows si True.
    - ``instance``:           Instancia de SQL Server (ej: 'SQLEXPRESS').
    - ``dump_mode``:          'sqlcmd' (defecto) | 'bcp'.
"""

import logging
import os
from pathlib import Path

from src.connectors.base import BaseConnector

log = logging.getLogger(__name__)

SQLCMD_BINARY = "sqlcmd.exe" if os.name == "nt" else "sqlcmd"


class SQLServerConnector(BaseConnector):
    """Conector para Microsoft SQL Server via sqlcmd o BCP."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1433,
        database: str = "",
        user: str | None = None,
        password: str | None = None,
        extra_params: dict | None = None,
    ) -> None:
        """
        Inicializa el conector de SQL Server.

        Args:
            host:         Host o IP del servidor SQL Server.
            port:         Puerto (defecto 1433).
            database:     Nombre de la BD.
            user:         Usuario SQL Server (None si usa autenticación Windows).
            password:     Contraseña (None si usa autenticación Windows).
            extra_params: Parámetros adicionales (ver módulo docstring).
        """
        pass

    def test_connection(self) -> bool:
        """
        Verifica la conexión a SQL Server usando pyodbc.

        Construye el connection string de ODBC según el modo de autenticación
        configurado (SQL Server o Windows integrada).

        Returns:
            bool: ``True`` si la conexión es válida.
        """
        pass

    def dump(self, output_path: Path) -> Path:
        """
        Genera el dump de SQL Server usando sqlcmd o BCP según configuración.

        En modo ``sqlcmd``, genera un script T-SQL con:
        - CREATE TABLE para cada tabla.
        - INSERT INTO para cada fila de datos.
        - Stored procedures, views y triggers si están disponibles.

        Args:
            output_path: Ruta donde guardar el archivo de dump (``.sql`` o ``.bcp``).

        Returns:
            Path: Ruta al archivo generado.
        """
        pass

    def get_dump_filename(self) -> str:
        """
        Devuelve el nombre sugerido del archivo de dump.

        Formato: ``{database}_{YYYYMMDD_HHMMSS}.sql``
        """
        pass

    def _build_odbc_connection_string(self) -> str:
        """
        Construye el string de conexión ODBC para pyodbc.

        Soporta autenticación SQL Server y Windows Integrated Security.

        Returns:
            str: Connection string de ODBC listo para usar con pyodbc.
        """
        pass

    def _dump_with_sqlcmd(self, output_path: Path) -> Path:
        """
        Genera el dump usando sqlcmd con un script T-SQL.

        Ejecuta múltiples queries para extraer el esquema y los datos,
        redirigiendo la salida al archivo de dump.

        Args:
            output_path: Archivo de destino.

        Returns:
            Path: Archivo de dump generado.
        """
        pass
