"""Pruebas de sync nuclear (vaciar destino + copytree)."""
from pathlib import Path

from src.core.folder_mirror import sync_nuclear_clone


def test_sync_nuclear_empties_dest_then_clones(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "keep.txt").write_text("new", encoding="utf-8")
    (src / "sub").mkdir()
    (src / "sub" / "inner.txt").write_text("inner", encoding="utf-8")
    dst.mkdir()
    (dst / "keep.txt").write_text("old", encoding="utf-8")
    (dst / "orphan_dir").mkdir()
    (dst / "orphan_dir" / "gone.txt").write_text("x", encoding="utf-8")
    (dst / "stale.txt").write_text("y", encoding="utf-8")

    sync_nuclear_clone(src, dst)

    assert (dst / "keep.txt").read_text(encoding="utf-8") == "new"
    assert (dst / "sub" / "inner.txt").read_text(encoding="utf-8") == "inner"
    assert not (dst / "orphan_dir").exists()
    assert not (dst / "stale.txt").exists()


def test_clean_display_name_discovery() -> None:
    from src.core.discovery import _clean_display_name

    assert _clean_display_name("🐘 PostgreSQL") == "PostgreSQL"
    assert _clean_display_name("Mongo 🍃 DB") == "Mongo DB"
