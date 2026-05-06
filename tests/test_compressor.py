import tarfile
import zipfile
from pathlib import Path

from src.storage.compressor import BackupCompressor


def test_compress_to_zip(tmp_path: Path) -> None:
    """Prueba la compresión de un directorio a ZIP."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "test.txt").write_text("hello world")

    dest_zip = tmp_path / "backup.zip"
    result = BackupCompressor.compress_to_zip(source_dir, dest_zip)

    assert result == dest_zip
    assert dest_zip.exists()
    assert zipfile.is_zipfile(dest_zip)


def test_compress_to_targz(tmp_path: Path) -> None:
    """Prueba la compresión de un directorio a TAR.GZ."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "test.txt").write_text("hello world")

    dest_tar = tmp_path / "backup.tar.gz"
    result = BackupCompressor.compress_to_targz(source_dir, dest_tar)

    assert result == dest_tar
    assert dest_tar.exists()
    assert tarfile.is_tarfile(dest_tar)
