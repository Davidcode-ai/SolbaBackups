"""
src/processors/compressor.py — Compresor de Archivos de Backup.

Proporciona la clase ``Compressor`` que comprime el archivo de dump
generado por el conector antes de enviarlo al destino.

Formatos soportados:
    - ``zip``: Archivo ZIP estándar usando ``zipfile``. Compatible con
               todas las versiones de Windows sin software adicional.
               Soporta compresión DEFLATE con nivel configurable.

    - ``gz``:  Archivo GZIP usando ``gzip``. Más eficiente en tamaño
               para dumps SQL de texto plano. No es nativo en Windows
               sin 7-Zip o WinZip, pero es estándar en Linux.

Nivel de compresión:
    Configurable de 1 (más rápido) a 9 (máxima compresión).
    Por defecto: 6 (equilibrio velocidad/tamaño, igual que gzip estándar).

Estrategia de nombre de archivo:
    El archivo comprimido mantiene el nombre del dump original más la
    extensión del formato: ``{dump_name}.zip`` o ``{dump_name}.gz``.

Rendimiento:
    Para dumps grandes (>1 GB), usa ``shutil.copyfileobj`` con chunks
    para no cargar todo el archivo en memoria.
"""

import gzip
import logging
import shutil
import zipfile
from pathlib import Path

log = logging.getLogger(__name__)

# Niveles de compresión disponibles (1=más rápido, 9=máxima compresión)
DEFAULT_COMPRESSION_LEVEL: int = 6
SUPPORTED_FORMATS: frozenset[str] = frozenset({"zip", "gz"})


class Compressor:
    """
    Compresor de archivos de backup con soporte ZIP y GZIP.

    Diseñado para ser stateless: cada llamada a ``compress()`` es independiente.
    """

    def __init__(
        self,
        fmt: str = "zip",
        level: int = DEFAULT_COMPRESSION_LEVEL,
    ) -> None:
        """
        Inicializa el compresor con el formato y nivel de compresión.

        Args:
            fmt:   Formato de compresión: 'zip' | 'gz'.
            level: Nivel de compresión de 1 (rápido) a 9 (máximo).

        Raises:
            ValueError: Si el formato no está soportado.
            ValueError: Si el nivel no está en el rango 1-9.
        """
        pass

    def compress(self, source_path: Path, output_dir: Path | None = None) -> Path:
        """
        Comprime un archivo y devuelve la ruta al archivo comprimido.

        Si ``output_dir`` es ``None``, el archivo comprimido se crea en el
        mismo directorio que ``source_path``.

        Args:
            source_path: Ruta al archivo a comprimir. Debe existir.
            output_dir:  Directorio donde crear el archivo comprimido.
                         Si es ``None``, usa el directorio del archivo fuente.

        Returns:
            Path: Ruta al archivo comprimido creado.

        Raises:
            FileNotFoundError: Si ``source_path`` no existe.
            ValueError:        Si el formato configurado no está soportado.
        """
        pass

    def _compress_zip(self, source_path: Path, output_path: Path) -> Path:
        """
        Comprime el archivo usando ZIP con compresión DEFLATE.

        El archivo dentro del ZIP mantiene el mismo nombre que el original
        (sin rutas absolutas) para que al descomprimir no cree subdirectorios
        inesperados.

        Args:
            source_path: Archivo a comprimir.
            output_path: Ruta del archivo ZIP de salida.

        Returns:
            Path: Ruta al ZIP creado.
        """
        pass

    def _compress_gz(self, source_path: Path, output_path: Path) -> Path:
        """
        Comprime el archivo usando GZIP con lectura por chunks.

        Lee el archivo fuente en bloques de 4 MB para minimizar el uso
        de memoria con dumps muy grandes.

        Args:
            source_path: Archivo a comprimir.
            output_path: Ruta del archivo .gz de salida.

        Returns:
            Path: Ruta al archivo .gz creado.
        """
        pass

    @staticmethod
    def get_output_extension(fmt: str) -> str:
        """
        Devuelve la extensión de archivo para el formato dado.

        Args:
            fmt: Formato de compresión ('zip' o 'gz').

        Returns:
            str: Extensión con punto ('.zip' o '.gz').
        """
        pass

    @staticmethod
    def decompress(compressed_path: Path, output_dir: Path) -> Path:
        """
        Descomprime un archivo ZIP o GZ en el directorio indicado.

        Detecta automáticamente el formato por la extensión del archivo.
        Usado en el flujo de restauración (no en backup).

        Args:
            compressed_path: Ruta al archivo comprimido.
            output_dir:      Directorio donde extraer el contenido.

        Returns:
            Path: Ruta al archivo descomprimido.

        Raises:
            ValueError: Si el formato no se reconoce por la extensión.
        """
        pass
