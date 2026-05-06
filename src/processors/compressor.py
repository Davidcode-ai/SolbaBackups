"""
src/processors/compressor.py — Compresor de Archivos de Backup.

Esta versión implementa la compresión nativa en ZIP usando la
librería estándar de Python (zipfile).
"""

import logging
import zipfile
from pathlib import Path

log = logging.getLogger(__name__)

class Compressor:
    """
    Gestor de compresión de archivos de backup.
    """

    def __init__(self, fmt: str = "zip", level: int = zipfile.ZIP_DEFLATED) -> None:
        """
        Inicializa el compresor.
        """
        self.fmt = fmt
        self.compression = level

    def compress(self, source_path: Path, output_dir: Path | None = None) -> Path:
        """
        Comprime un archivo y devuelve la ruta al archivo comprimido en ZIP.

        Args:
            source_path: Ruta al archivo a comprimir.
            output_dir: Directorio de destino (opcional). Si no se provee,
                        se usa el mismo directorio que source_path.

        Returns:
            Path: Ruta del archivo .zip generado.
        """
        if not source_path.exists():
            raise FileNotFoundError(f"El archivo fuente no existe: {source_path}")

        if output_dir is None:
            output_dir = source_path.parent
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Nombre de salida: original + .zip
        output_name = f"{source_path.name}.zip"
        output_path = output_dir / output_name

        log.info(f"Comprimiendo {source_path.name} a {output_name}...")
        
        try:
            # Comprimir usando DEFLATE
            with zipfile.ZipFile(output_path, 'w', compression=self.compression) as zf:
                # El parámetro arcname evita que se guarde la ruta absoluta dentro del zip
                zf.write(source_path, arcname=source_path.name)
            
            log.info(f"Compresión exitosa: {output_path}")
            return output_path
            
        except Exception as e:
            log.error(f"Error comprimiendo el archivo {source_path}: {e}")
            if output_path.exists():
                output_path.unlink() # Limpiar archivo corrupto
            raise
