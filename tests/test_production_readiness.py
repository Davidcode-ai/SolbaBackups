"""
Tests de auditoría pre-producción: sync estricto, restauración, notificaciones HTML y rutas.

No modifican lógica de negocio; documentan comportamiento esperado del código congelado.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.job_manager import JobManager
from src.core.history_manager import HistoryManager
from src.core import notifications as notif_mod
from src.db import crud


# ---------------------------------------------------------------------------
# _execute_pure_sync
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_pure_sync_mirrors_to_dest_root(db_session, tmp_path):
    """Espejo: vacía destino y copia entradas de src en la raíz."""
    src = tmp_path / "src_root"
    dst = tmp_path / "dst_root"
    src.mkdir()
    dst.mkdir()
    (src / "marker.dat").write_text("ok", encoding="utf-8")
    (dst / "stale.txt").write_text("old", encoding="utf-8")

    job = crud.job_create(
        db_session,
        {
            "name": "PureSyncJob",
            "db_type": "sync",
            "db_name": str(src),
            "dest_local_path": str(dst),
            "dest_type": "local",
            "compress": False,
        },
    )
    hm = HistoryManager()
    run = hm.start_run(db_session, job.id, job.name, "manual")
    mgr = JobManager()
    size, final = await mgr._execute_pure_sync(job, run, db_session)
    assert Path(final).resolve() == dst.resolve()
    assert (dst / "marker.dat").read_text(encoding="utf-8") == "ok"
    assert not (dst / "stale.txt").exists()
    assert size > 0


@pytest.mark.asyncio
async def test_execute_pure_sync_strips_dest_when_last_segment_matches_job_name(
    db_session, tmp_path
):
    """Si dest_local_path termina en carpeta con nombre de la tarea, se usa el padre."""
    job_name = "café_demo_job"
    src = tmp_path / "src_u"
    src.mkdir()
    (src / "x.txt").write_text("1", encoding="utf-8")
    parent = tmp_path / "real_dest"
    parent.mkdir()
    wrong_leaf = parent / job_name
    wrong_leaf.mkdir()

    job = crud.job_create(
        db_session,
        {
            "name": job_name,
            "db_type": "sync",
            "db_name": str(src),
            "dest_local_path": str(wrong_leaf),
            "dest_type": "local",
            "compress": False,
        },
    )
    run = HistoryManager().start_run(db_session, job.id, job.name, "manual")
    await JobManager()._execute_pure_sync(job, run, db_session)
    assert (parent / "x.txt").read_text(encoding="utf-8") == "1"


@pytest.mark.asyncio
async def test_execute_pure_sync_unicode_and_long_path_segment(db_session, tmp_path):
    """Rutas con Unicode y segmento largo (simula entornos Windows problemáticos)."""
    long_seg = "a" * 80 + "_Ω_测试"
    src = tmp_path / "s_unicode" / long_seg
    dst = tmp_path / "d_unicode" / long_seg
    src.mkdir(parents=True)
    dst.mkdir(parents=True)
    (src / "deep.txt").write_text("Σ", encoding="utf-8")

    job = crud.job_create(
        db_session,
        {
            "name": "UnicodeJob",
            "db_type": "sync",
            "db_name": str(src),
            "dest_local_path": str(dst),
            "dest_type": "local",
            "compress": False,
        },
    )
    run = HistoryManager().start_run(db_session, job.id, job.name, "manual")
    await JobManager()._execute_pure_sync(job, run, db_session)
    assert (dst / "deep.txt").read_text(encoding="utf-8") == "Σ"


# ---------------------------------------------------------------------------
# restore_backup (db_type definido; flujo sqlite desde ZIP)
# ---------------------------------------------------------------------------


def test_restore_backup_sqlite_from_zip_success(db_session, tmp_path):
    """restore_backup normaliza db_type y restaura un .db dentro de un ZIP."""
    original = tmp_path / "original_restore.db"
    conn = sqlite3.connect(str(original))
    conn.execute("CREATE TABLE t(x INTEGER)")
    conn.execute("INSERT INTO t VALUES (99)")
    conn.commit()
    conn.close()

    zip_path = tmp_path / "bak.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(original, arcname="original_restore.db")

    job = crud.job_create(
        db_session,
        {
            "name": "RestoreSqliteJob",
            "db_type": "SQLite",  # mayúsculas: debe normalizarse a sqlite
            "db_name": str(original),
            "dest_local_path": str(tmp_path),
            "dest_type": "local",
            "compress": False,
        },
    )
    hm = HistoryManager()
    run = hm.start_run(db_session, job.id, job.name, "manual")
    hm.finish_run(
        db_session,
        run.id,
        "success",
        file_size_bytes=zip_path.stat().st_size,
        backup_file_path=str(zip_path),
    )

    mgr = JobManager()
    out = mgr.restore_backup(run.id)
    assert out["success"] is True
    assert out["db_type"] == "sqlite"

    conn2 = sqlite3.connect(str(original))
    row = conn2.execute("SELECT x FROM t").fetchone()
    conn2.close()
    assert row == (99,)


def test_restore_backup_fails_if_run_not_success(db_session, tmp_path):
    job = crud.job_create(
        db_session,
        {"name": "BadRun", "db_type": "folder", "db_name": str(tmp_path)},
    )
    run = HistoryManager().start_run(db_session, job.id, job.name, "manual")
    HistoryManager().finish_run(db_session, run.id, "failed", error_message="x")
    with pytest.raises(ValueError, match="SUCCESS"):
        JobManager().restore_backup(run.id)


# ---------------------------------------------------------------------------
# notifications HTML
# ---------------------------------------------------------------------------


def test_render_backup_report_html_escapes_xss():
    """La plantilla escapa nombre de job y mensaje de error."""
    payload = "<script>alert(1)</script>"
    html = notif_mod.render_backup_report_html(
        success=False,
        job_name=payload,
        job_id=1,
        db_type="postgresql",
        destination_summary="/tmp",
        log_lines=["line1"],
        error_message=payload,
        size_display="1 KiB",
    )
    assert "<script>" not in html
    assert html_lib.escape(payload) in html or "&lt;script&gt;" in html


def test_render_backup_report_html_contains_corporate_structure():
    """Estructura visual acordada (fondo, cabecera, pre terminal)."""
    html = notif_mod.render_backup_report_html(
        success=True,
        job_name="J",
        job_id=1,
        db_type="sync",
        destination_summary="D:\\backups",
        log_lines=["[INFO] ok"],
        size_display="100 B",
    )
    assert "#f1f5f9" in html
    assert "#1e293b" in html
    assert "SolbaBackups" in html
    assert "#0f172a" in html
    assert "#4ade80" in html
    assert "<pre" in html


@pytest.mark.parametrize(
    "n,expected_sub",
    [
        (None, "N/D"),
        (0, "B"),
        (1024, "KiB"),
    ],
)
def test_format_bytes_display(n, expected_sub):
    s = notif_mod.format_bytes_display(n)
    assert expected_sub in s


def test_send_email_notification_builds_mime_html_parts():
    """Con html_body se usa multipart con MIMEText html."""
    with patch.object(notif_mod, "_resolve_smtp_config", return_value={
        "host": "h", "port": 587, "user": "u", "password": "p", "configured": True, "source": "env"
    }):
        mock_server = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_server):
            notif_mod.send_email_notification(
                "to@test.com",
                "Subj",
                "plain body",
                html_body="<p>hi</p>",
            )
    mock_server.send_message.assert_called_once()
    msg = mock_server.send_message.call_args[0][0]
    assert msg.get_content_subtype() == "alternative"
    parts = list(msg.walk())
    types = {p.get_content_type() for p in parts}
    assert "text/plain" in types
    assert "text/html" in types
