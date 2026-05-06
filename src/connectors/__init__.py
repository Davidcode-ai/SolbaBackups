"""
src/connectors/__init__.py

Paquete de conectores de bases de datos para SolbaBackups.

Cada conector sabe cómo conectarse a un motor de BD específico y
producir un archivo de dump listo para ser procesado.

Exports públicos:
    - BaseConnector  : Clase abstracta base.
    - PostgreSQLConnector : Conector para PostgreSQL via pg_dump.
    - MySQLConnector      : Conector para MySQL/MariaDB via mysqldump.
    - SQLServerConnector  : Conector para SQL Server via sqlcmd/BCP.
    - SQLiteConnector     : Conector para SQLite via copia directa.
    - get_connector       : Factory function que resuelve el conector correcto.
"""

from src.connectors.base import BaseConnector
from src.connectors.mysql import MySQLConnector
from src.connectors.postgresql import PostgreSQLConnector
from src.connectors.sqlite import SQLiteConnector
from src.connectors.sqlserver import SQLServerConnector

__all__ = [
    "BaseConnector",
    "PostgreSQLConnector",
    "MySQLConnector",
    "SQLServerConnector",
    "SQLiteConnector",
    "get_connector",
]


def get_connector(db_type: str, **kwargs) -> "BaseConnector":
    """
    Factory function que instancia el conector correcto según el tipo de BD.

    Args:
        db_type: Identificador del motor de base de datos.
                 Valores aceptados: 'postgresql', 'mysql', 'sqlserver', 'sqlite'.
        **kwargs: Parámetros de conexión (host, port, user, password, database, etc.)
                  que se pasan directamente al constructor del conector elegido.

    Returns:
        BaseConnector: Instancia del conector correspondiente al motor indicado.

    Raises:
        ValueError: Si ``db_type`` no corresponde a ningún conector registrado.
    """
    pass
