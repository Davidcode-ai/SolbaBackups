"""
src/connectors/base.py — Clase Abstracta Base para Conectores de BD.

Define el contrato que deben cumplir todos los conectores de bases de datos.
Cada motor de BD (PostgreSQL, MySQL, SQL Server, SQLite) implementa
esta interfaz para garantizar que el ``JobManager`` pueda usarlos
de forma intercambiable (patrón Strategy).

Contrato del conector:
    1. ``test_connection()`` : Verifica que las credenciales son válidas.
    2. ``dump(output_path)`` : Genera el archivo de dump y lo guarda en ``output_path``.
    3. ``get_dump_filename()``: Sugiere el nombre de archivo estándar del dump.

Parámetros de conexión:
    Se pasan al constructor como kwargs y se almacenan en atributos protegidos.
    La contraseña siempre se recibe en claro (desencriptada por el JobManager
    antes de instanciar el conector).
"""

import abc
import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class BaseConnector(abc.ABC):
    """
    Clase abstracta que define la interfaz común de todos los conectores.

    Atributos de instancia (configurados en ``__init__`` de cada subclase):
        _host     : Hostname o IP del servidor de BD.
        _port     : Puerto TCP del servidor.
        _database : Nombre de la base de datos.
        _user     : Usuario de conexión.
        _password : Contraseña en claro (en memoria, no persistida).
        _extra    : Diccionario con parámetros adicionales (ssl, charset, etc.).
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str = "",
        user: str | None = None,
        password: str | None = None,
        extra_params: dict | None = None,
    ) -> None:
        """
        Inicializa los parámetros comunes de conexión.

        Args:
            host:         Hostname o IP del servidor (None para BD locales como SQLite).
            port:         Puerto TCP del servidor (None para BD locales).
            database:     Nombre de la BD o ruta al archivo (SQLite).
            user:         Usuario de autenticación.
            password:     Contraseña en texto claro (se mantiene solo en memoria).
            extra_params: Parámetros adicionales específicos del motor.
        """
        pass

    @abc.abstractmethod
    def test_connection(self) -> bool:
        """
        Verifica que las credenciales y la conexión son válidas.

        Intenta establecer una conexión real con el servidor de BD y la
        cierra inmediatamente. No lanza excepciones: devuelve ``True``
        si la conexión fue exitosa, ``False`` en caso contrario.

        Returns:
            bool: ``True`` si la conexión es válida, ``False`` si falla.
        """
        pass

    @abc.abstractmethod
    def dump(self, output_path: Path) -> Path:
        """
        Genera un dump completo de la base de datos.

        Ejecuta la herramienta de dump correspondiente al motor (pg_dump,
        mysqldump, sqlcmd, etc.) y guarda el resultado en ``output_path``.

        Args:
            output_path: Ruta completa donde guardar el archivo de dump.
                         El directorio padre debe existir previamente.

        Returns:
            Path: Ruta al archivo de dump generado (puede diferir de
                  ``output_path`` si la herramienta añade extensión).

        Raises:
            ConnectionError: Si no se puede conectar al servidor.
            RuntimeError:    Si la herramienta de dump retorna error.
            FileNotFoundError: Si la herramienta (pg_dump, etc.) no está en el PATH.
        """
        pass

    @abc.abstractmethod
    def get_dump_filename(self) -> str:
        """
        Sugiere un nombre de archivo estándar para el dump.

        El nombre sigue el patrón: ``{database}_{timestamp}.{ext}``
        donde ``{ext}`` es la extensión nativa del formato de dump
        del motor (sql, bak, db, etc.).

        Returns:
            str: Nombre de archivo sugerido sin ruta (solo el basename).
        """
        pass

    def _run_subprocess(
        self,
        cmd: list[str],
        env: dict | None = None,
        timeout: int = 3600,
    ) -> subprocess.CompletedProcess:
        """
        Ejecuta un subproceso de forma segura con timeout y captura de errores.

        Método helper compartido por todos los conectores que usan herramientas
        externas (pg_dump, mysqldump, sqlcmd). Oculta la contraseña del log.

        Args:
            cmd:     Lista de strings con el comando y sus argumentos.
            env:     Variables de entorno para el subproceso (ej: PGPASSWORD).
            timeout: Timeout máximo en segundos (defecto: 60 minutos).

        Returns:
            subprocess.CompletedProcess: Resultado del proceso.

        Raises:
            FileNotFoundError: Si el ejecutable del comando no se encuentra.
            RuntimeError:      Si el proceso termina con código de error != 0.
            TimeoutError:      Si el proceso supera el timeout.
        """
        pass
