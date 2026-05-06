"""
Tests del módulo de sincronización de carpetas.
"""

import time
from pathlib import Path

import pytest

from src.sync.folder_sync import FolderSync


@pytest.fixture()
def source_folder(tmp_path) -> Path:
    folder = tmp_path / "source"
    folder.mkdir()
    (folder / "a.txt").write_text("Archivo A")
    (folder / "b.txt").write_text("Archivo B")
    sub = folder / "subdir"
    sub.mkdir()
    (sub / "c.txt").write_text("Archivo C")
    return folder


@pytest.fixture()
def dest_folder(tmp_path) -> Path:
    folder = tmp_path / "dest"
    folder.mkdir()
    return folder


class TestFolderSyncUpdate:
    def test_copies_new_files(self, source_folder, dest_folder):
        fs = FolderSync(source_folder, dest_folder, mode="update")
        copied, updated, deleted = fs.sync()

        assert copied == 3  # a.txt, b.txt, subdir/c.txt
        assert updated == 0
        assert deleted == 0
        assert (dest_folder / "a.txt").exists()
        assert (dest_folder / "subdir" / "c.txt").exists()

    def test_updates_modified_files(self, source_folder, dest_folder):
        fs = FolderSync(source_folder, dest_folder, mode="update")
        fs.sync()

        # Modificar un archivo en origen (actualizar mtime)
        src_file = source_folder / "a.txt"
        src_file.write_text("Contenido actualizado")
        # Forzar mtime más reciente
        future_mtime = time.time() + 10
        import os

        os.utime(src_file, (future_mtime, future_mtime))

        copied, updated, deleted = fs.sync()
        assert updated == 1
        assert (dest_folder / "a.txt").read_text() == "Contenido actualizado"

    def test_does_not_delete_in_update_mode(self, source_folder, dest_folder):
        """En modo 'update' no se eliminan archivos del destino."""
        extra = dest_folder / "extra.txt"
        extra.write_text("extra")

        fs = FolderSync(source_folder, dest_folder, mode="update")
        copied, updated, deleted = fs.sync()

        assert deleted == 0
        assert extra.exists()


class TestFolderSyncMirror:
    def test_deletes_extra_in_dest(self, source_folder, dest_folder):
        """En modo 'mirror', los archivos extra en destino se eliminan."""
        extra = dest_folder / "orphan.txt"
        extra.write_text("huérfano")

        fs = FolderSync(source_folder, dest_folder, mode="mirror")
        copied, updated, deleted = fs.sync()

        assert deleted == 1
        assert not extra.exists()

    def test_mirrors_complete_structure(self, source_folder, dest_folder):
        fs = FolderSync(source_folder, dest_folder, mode="mirror")
        fs.sync()

        assert (dest_folder / "a.txt").exists()
        assert (dest_folder / "b.txt").exists()
        assert (dest_folder / "subdir" / "c.txt").exists()


class TestFolderSyncExclusions:
    def test_excludes_pattern(self, source_folder, dest_folder):
        fs = FolderSync(
            source_folder, dest_folder, mode="update", exclude_patterns=["*.txt"]
        )
        copied, updated, deleted = fs.sync()
        assert copied == 0

    def test_partial_exclusion(self, source_folder, dest_folder):
        # Añadir un archivo .log
        (source_folder / "debug.log").write_text("log content")

        fs = FolderSync(
            source_folder, dest_folder, mode="update", exclude_patterns=["*.log"]
        )
        copied, updated, deleted = fs.sync()

        assert not (dest_folder / "debug.log").exists()
        assert (dest_folder / "a.txt").exists()


class TestFolderSyncNonexistentSource:
    def test_raises_for_missing_source(self, tmp_path):
        fs = FolderSync(
            source=tmp_path / "nonexistent",
            destination=tmp_path / "dest",
            mode="update",
        )
        with pytest.raises(FileNotFoundError):
            fs.sync()
