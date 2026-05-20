"""
Sincronización unidireccional (espejo): destino = copia exacta del origen.

- Archivos nuevos o modificados en origen se copian (sobrescribiendo en destino).
- Archivos que ya no existen en origen se eliminan del destino.
- Directorios vacíos sobrantes se eliminan de abajo hacia arriba.
"""
from __future__ import annotations

import filecmp
import logging
import shutil
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

LogFn = Callable[[str], None]


def mirror_unidirectional(
    src: Path,
    dst: Path,
    log_fn: LogFn | None = None,
) -> tuple[int, int, int]:
    """
    Args:
        src: Carpeta origen (debe existir y ser directorio).
        dst: Carpeta destino (se crea si no existe).

    Returns:
        Tupla (copiados_nuevos, sobrescritos, eliminados_en_destino).
    """
    def _log(msg: str) -> None:
        if log_fn:
            log_fn(msg)
        else:
            log.info(msg)

    src = src.resolve()
    dst = dst.resolve()

    if not src.is_dir():
        raise NotADirectoryError(f"Origen no es un directorio: {src}")

    dst.mkdir(parents=True, exist_ok=True)

    # Mapa rel_posix -> Path origen
    src_files: dict[str, Path] = {}
    for p in src.rglob("*"):
        if p.is_file():
            rel = p.relative_to(src).as_posix()
            src_files[rel] = p

    copied = 0
    overwritten = 0

    for rel, sp in src_files.items():
        dp = dst / rel
        dp.parent.mkdir(parents=True, exist_ok=True)

        if not dp.exists():
            shutil.copy2(sp, dp)
            copied += 1
            continue

        if not dp.is_file():
            shutil.copy2(sp, dp)
            overwritten += 1
            continue

        try:
            s_stat = sp.stat()
            d_stat = dp.stat()
        except OSError:
            shutil.copy2(sp, dp)
            overwritten += 1
            continue

        same_size_mtime = (
            s_stat.st_size == d_stat.st_size
            and int(s_stat.st_mtime_ns) == int(d_stat.st_mtime_ns)
        )
        if same_size_mtime:
            continue

        if s_stat.st_size != d_stat.st_size or s_stat.st_mtime > d_stat.st_mtime:
            shutil.copy2(sp, dp)
            overwritten += 1
            continue

        if filecmp.cmp(sp, dp, shallow=False):
            continue

        shutil.copy2(sp, dp)
        overwritten += 1

    deleted = 0
    # Borrar archivos en destino que no están en origen
    for p in list(dst.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(dst).as_posix()
        if rel not in src_files:
            try:
                p.unlink()
                deleted += 1
            except OSError as e:
                _log(f"No se pudo eliminar '{p}': {e}")

    # Eliminar directorios vacíos (excepto la raíz dest), de profundo a superficial
    all_dirs = sorted(
        (p for p in dst.rglob("*") if p.is_dir()),
        key=lambda x: len(x.parts),
        reverse=True,
    )
    for d in all_dirs:
        if d == dst:
            continue
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass

    _log(
        f"Espejo completado: nuevos={copied}, actualizados={overwritten}, "
        f"eliminados_en_destino={deleted}"
    )
    return copied, overwritten, deleted
