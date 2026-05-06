"""
Módulo para la compresión de copias de seguridad.
"""

import logging
import os
import tarfile
import zipfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class BackupCompressor:
    """Clase para comprimir archivos y directorios de copias de seguridad."""

    @staticmethod
    def compress_to_zip(source_path: Path, dest_path: Path) -> Optional[Path]:
        """
        Comprime un archivo o directorio en formato ZIP.

        Args:
            source_path (Path): Ruta del archivo o directorio a comprimir.
            dest_path (Path): Ruta de destino del archivo ZIP resultante.

        Returns:
            Optional[Path]: La ruta del archivo comprimido, o None si falla.
        """
        try:
            with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                if source_path.is_file():
                    zipf.write(source_path, arcname=source_path.name)
                elif source_path.is_dir():
                    for root, _, files in os.walk(source_path):
                        for file in files:
                            file_path = Path(root) / file
                            # Mantener la estructura de directorios relativa al origen
                            arcname = file_path.relative_to(source_path.parent)
                            zipf.write(file_path, arcname=arcname)
                else:
                    logger.error("La ruta origen no existe: %s", source_path)
                    return None

            logger.info("Compresión ZIP completada: %s", dest_path)
            return dest_path
        except Exception as exc:
            logger.error("Error al comprimir en ZIP: %s", exc)
            return None

    @staticmethod
    def compress_to_targz(source_path: Path, dest_path: Path) -> Optional[Path]:
        """
        Comprime un archivo o directorio en formato TAR.GZ.

        Args:
            source_path (Path): Ruta del archivo o directorio a comprimir.
            dest_path (Path): Ruta de destino del archivo TAR.GZ resultante.

        Returns:
            Optional[Path]: La ruta del archivo comprimido, o None si falla.
        """
        try:
            with tarfile.open(dest_path, "w:gz") as tarf:
                arcname = source_path.name
                tarf.add(source_path, arcname=arcname)

            logger.info("Compresión TAR.GZ completada: %s", dest_path)
            return dest_path
        except Exception as exc:
            logger.error("Error al comprimir en TAR.GZ: %s", exc)
            return None
