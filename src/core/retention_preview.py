"""
Vista previa de la política de retención (sin borrar archivos).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _file_entry(
    name: str,
    size_bytes: int,
    reference_time: datetime,
    retention_days: int,
    path: str | None = None,
    source: str = "local",
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    ref_utc = reference_time if reference_time.tzinfo else reference_time.replace(tzinfo=timezone.utc)
    would_delete = ref_utc <= cutoff
    delete_after = ref_utc + timedelta(days=retention_days)
    return {
        "name": name,
        "path": path,
        "size_bytes": size_bytes,
        "reference_at": ref_utc.isoformat(),
        "status": "delete_now" if would_delete else "keep",
        "delete_after": None if would_delete else delete_after.isoformat(),
        "source": source,
    }


def preview_local_retention(destination_path: str, retention_days: int) -> dict[str, Any]:
    """Lista .zip en carpeta local y clasifica según días de retención."""
    dest_dir = Path(destination_path)
    if retention_days <= 0:
        files = []
        if dest_dir.exists():
            for fp in sorted(dest_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
                if fp.is_file():
                    st = fp.stat()
                    files.append(
                        {
                            "name": fp.name,
                            "path": str(fp),
                            "size_bytes": st.st_size,
                            "reference_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                            "status": "keep",
                            "delete_after": None,
                            "source": "local",
                        }
                    )
        return {
            "dest_type": "local",
            "dest_label": str(dest_dir),
            "retention_days": retention_days,
            "policy_active": False,
            "files_to_delete": [],
            "files_kept": files,
            "note": "Retención desactivada (0 días). No se borrará nada automáticamente.",
        }

    if not dest_dir.exists():
        return {
            "dest_type": "local",
            "dest_label": str(dest_dir),
            "retention_days": retention_days,
            "policy_active": True,
            "files_to_delete": [],
            "files_kept": [],
            "note": "La carpeta de destino aún no existe. Tras el primer backup aparecerán archivos aquí.",
        }

    to_delete: list[dict] = []
    kept: list[dict] = []
    for fp in sorted(dest_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        if not fp.is_file():
            continue
        st = fp.stat()
        ref = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        entry = _file_entry(fp.name, st.st_size, ref, retention_days, path=str(fp))
        if entry["status"] == "delete_now":
            to_delete.append(entry)
        else:
            kept.append(entry)

    note = (
        f"En la próxima ejecución del backup se borrarán {len(to_delete)} archivo(s) "
        f"con más de {retention_days} día(s) de antigüedad (fecha de modificación del .zip)."
        if to_delete
        else f"Ningún archivo supera {retention_days} día(s). La limpieza se revisa al final de cada backup."
    )
    return {
        "dest_type": "local",
        "dest_label": str(dest_dir),
        "retention_days": retention_days,
        "policy_active": True,
        "files_to_delete": to_delete,
        "files_kept": kept,
        "note": note,
    }


def preview_gdrive_retention(
    folder_id: str | None,
    job_name: str,
    retention_days: int,
) -> dict[str, Any]:
    """Vista previa en Google Drive (solo lectura)."""
    if retention_days <= 0:
        return {
            "dest_type": "google_drive",
            "dest_label": job_name or "Google Drive",
            "retention_days": retention_days,
            "policy_active": False,
            "files_to_delete": [],
            "files_kept": [],
            "note": "Retención desactivada (0 días).",
        }

    try:
        from src.destinations.google_drive import GoogleDriveDestination

        dest = GoogleDriveDestination(
            folder_id=folder_id,
            retention_days=retention_days,
            job_name=job_name or "backup",
        )
        backups = dest.list_backups()
    except Exception as exc:
        return {
            "dest_type": "google_drive",
            "dest_label": job_name or "Google Drive",
            "retention_days": retention_days,
            "policy_active": True,
            "files_to_delete": [],
            "files_kept": [],
            "note": f"No se pudo consultar Drive: {exc}",
        }

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    to_delete: list[dict] = []
    kept: list[dict] = []

    for item in backups:
        name = item.get("name") or "?"
        size = int(item.get("size_bytes") or item.get("size") or 0)
        created_raw = item.get("created_at") or item.get("createdTime") or ""
        if isinstance(created_raw, datetime):
            ref = created_raw if created_raw.tzinfo else created_raw.replace(tzinfo=timezone.utc)
        else:
            try:
                ref = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
            except ValueError:
                ref = datetime.now(timezone.utc)
        entry = _file_entry(name, size, ref, retention_days, source="google_drive")
        if entry["status"] == "delete_now":
            to_delete.append(entry)
        else:
            kept.append(entry)

    note = (
        f"En la próxima ejecución se eliminarían {len(to_delete)} archivo(s) en Drive "
        f"(criterio: createdTime > {retention_days} días)."
        if to_delete
        else f"Ningún archivo en Drive supera {retention_days} día(s) según createdTime."
    )
    return {
        "dest_type": "google_drive",
        "dest_label": job_name or "Google Drive",
        "retention_days": retention_days,
        "policy_active": True,
        "files_to_delete": to_delete,
        "files_kept": kept,
        "note": note,
    }
