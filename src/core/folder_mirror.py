"""
Sincronización literal (modo sync): vacía el destino y copia el árbol del origen.

Estrategia «nuclear» solicitada:
1) Borrar solo el *contenido* de la carpeta destino (raíz intacta).
2) Copiar solo el *contenido* del origen: cada entrada de ``src`` va directamente bajo ``dst``
   (equivalente a copytree con dest vacío; evita cualquier carpeta extra con el nombre del origen).
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

LogFn = Callable[[str], None]


def sync_nuclear_clone(
    src: Path,
    dst: Path,
    log_fn: LogFn | None = None,
) -> tuple[int, int, int]:
    """
    Vacía ``dst`` (sin eliminar la carpeta raíz) y copia todo ``src`` dentro de ``dst``.

    Returns:
        (archivos_en_destino_tras_copiar, 0, entradas_eliminadas_en_raíz_destino)
    """
    def _log(msg: str) -> None:
        if log_fn:
            log_fn(msg)
        else:
            log.info(msg)

    src = src.expanduser().resolve()
    dst = dst.expanduser().resolve()

    if not src.is_dir():
        raise NotADirectoryError(f"Origen no es un directorio: {src}")
    if src == dst:
        raise ValueError("Origen y destino no pueden ser la misma ruta.")

    dst.mkdir(parents=True, exist_ok=True)

    removed_root_entries = 0
    for child in list(dst.iterdir()):
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                os.remove(child)
            removed_root_entries += 1
        except OSError as exc:
            _log(f"No se pudo eliminar '{child}': {exc}")
            raise RuntimeError(
                f"No se pudo vaciar el destino antes del sync: {child}"
            ) from exc

    _log(
        f"Sync nuclear: eliminadas {removed_root_entries} entradas en la raíz del destino; "
        f"copiando contenido de {src} dentro de {dst}..."
    )
    for entry in src.iterdir():
        target = dst / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)

    file_count = sum(1 for p in dst.rglob("*") if p.is_file())
    _log(f"Sync nuclear completado: {file_count} archivos bajo {dst}.")

    return (file_count, 0, removed_root_entries)
