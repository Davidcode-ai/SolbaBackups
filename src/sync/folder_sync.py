"""
Sincronización bidireccional y unidireccional de carpetas.

Modos disponibles:
  - mirror  : origen → destino (elimina en destino lo que no está en origen)
  - update  : solo copia archivos nuevos o más recientes
  - watch   : monitoriza en tiempo real (usando watchdog)
"""

from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FolderSync:
    """Sincroniza dos carpetas según el modo seleccionado."""

    def __init__(
        self,
        source: Path,
        destination: Path,
        mode: str = "update",
        exclude_patterns: Optional[List[str]] = None,
        on_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Args:
            source:           Carpeta de origen.
            destination:      Carpeta de destino.
            mode:             'mirror' | 'update' | 'watch'
            exclude_patterns: Patrones glob a excluir.
            on_change:        Callback invocado con el path modificado
                              (solo para modo 'watch').
        """
        self.source = Path(source)
        self.destination = Path(destination)
        self.mode = mode.lower()
        self.exclude_patterns: List[str] = exclude_patterns or []
        self.on_change = on_change
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Sincronización inmediata
    # ------------------------------------------------------------------
    def sync(self) -> Tuple[int, int, int]:
        """
        Ejecuta la sincronización.

        Returns:
            Tuple (copied, updated, deleted).
        """
        if not self.source.exists():
            raise FileNotFoundError(f"Carpeta origen no existe: {self.source}")
        self.destination.mkdir(parents=True, exist_ok=True)

        copied, updated, deleted = 0, 0, 0

        # Copiar/actualizar archivos de origen a destino
        for src_file in self.source.rglob("*"):
            if src_file.is_dir():
                continue
            if self._is_excluded(src_file):
                continue

            rel = src_file.relative_to(self.source)
            dst_file = self.destination / rel

            if not dst_file.exists():
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                copied += 1
                logger.debug("Copiado: %s", rel)
            elif src_file.stat().st_mtime > dst_file.stat().st_mtime:
                shutil.copy2(src_file, dst_file)
                updated += 1
                logger.debug("Actualizado: %s", rel)

        # Modo mirror: eliminar en destino lo que no existe en origen
        if self.mode == "mirror":
            for dst_file in self.destination.rglob("*"):
                if dst_file.is_dir():
                    continue
                rel = dst_file.relative_to(self.destination)
                src_file = self.source / rel
                if not src_file.exists():
                    dst_file.unlink()
                    deleted += 1
                    logger.debug("Eliminado (mirror): %s", rel)
            # Limpiar directorios vacíos
            for dst_dir in sorted(
                self.destination.rglob("*"), key=lambda p: len(p.parts), reverse=True
            ):
                if dst_dir.is_dir() and not any(dst_dir.iterdir()):
                    dst_dir.rmdir()

        logger.info(
            "Sync %s → %s: %d copiados, %d actualizados, %d eliminados.",
            self.source,
            self.destination,
            copied,
            updated,
            deleted,
        )
        return copied, updated, deleted

    # ------------------------------------------------------------------
    # Modo watch (tiempo real)
    # ------------------------------------------------------------------
    def start_watch(self) -> None:
        """Inicia la monitorización en tiempo real en un hilo daemon."""
        try:
            from watchdog.observers import Observer  # noqa: PLC0415
            from watchdog.events import FileSystemEventHandler  # noqa: PLC0415
        except ImportError:
            raise ImportError("watchdog no instalado. Ejecuta: pip install watchdog")

        sync_fn = self.sync
        on_change = self.on_change

        class _Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                if event.is_directory:
                    return
                logger.info("Cambio detectado: %s", event.src_path)
                if on_change:
                    on_change(event.src_path)
                sync_fn()

        observer = Observer()
        observer.schedule(_Handler(), str(self.source), recursive=True)
        observer.start()
        logger.info("Monitorización activa: %s → %s", self.source, self.destination)
        self._observer = observer  # guardamos referencia

    def stop_watch(self) -> None:
        """Detiene la monitorización."""
        if hasattr(self, "_observer") and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()
        logger.info("Monitorización detenida.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _is_excluded(self, file_path: Path) -> bool:
        rel = str(file_path.relative_to(self.source))
        for pattern in self.exclude_patterns:
            if file_path.match(pattern) or Path(rel).match(pattern):
                return True
        return False
