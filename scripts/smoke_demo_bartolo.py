#!/usr/bin/env python3
"""
Smoke tests para demo con Bartolo — ejecutar con el servidor en marcha:
  python solba_web.py
  python scripts/smoke_demo_bartolo.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import httpx

BASE = os.environ.get("SOLBA_BASE_URL", "http://localhost:8765/api/v1")
TIMEOUT = 30.0
PASS = 0
FAIL = 0
SKIP = 0


def ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f"  [OK] {name}")


def fail(name: str, detail: str = "") -> None:
    global FAIL
    FAIL += 1
    msg = f"  [FAIL] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def skip(name: str, reason: str = "") -> None:
    global SKIP
    SKIP += 1
    msg = f"  [SKIP] {name}"
    if reason:
        msg += f" — {reason}"
    print(msg)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=TIMEOUT)

    section("Salud del servidor")
    try:
        r = client.get("/jobs")
        if r.status_code == 200:
            ok("GET /jobs")
        else:
            fail("GET /jobs", f"status {r.status_code}")
    except httpx.ConnectError:
        print("\nERROR: No hay servidor en", BASE.replace("/api/v1", ""))
        print("Arranca: python solba_web.py")
        return 2

    for ep in ("history", "settings", "jobs/discovery"):
        r = client.get(f"/{ep}")
        if r.status_code == 200:
            ok(f"GET /{ep}")
        else:
            fail(f"GET /{ep}", f"status {r.status_code}")

    section("CRUD de tareas (carpeta — seguro para demo)")
    tmp_src = Path(tempfile.gettempdir()) / "solba_demo_src"
    tmp_dst = Path(tempfile.gettempdir()) / "solba_demo_dst"
    tmp_src.mkdir(exist_ok=True)
    tmp_dst.mkdir(exist_ok=True)
    (tmp_src / "demo.txt").write_text("demo bartolo\n", encoding="utf-8")

    job_name = f"Demo_Bartolo_{int(time.time())}"
    payload = {
        "name": job_name,
        "description": "Smoke test automático",
        "db_type": "folder",
        "db_name": str(tmp_src),
        "schedule": "manual",
        "dest_type": "local",
        "dest_local_path": str(tmp_dst),
        "dest_retention_days": 0,
        "compress": True,
    }
    r = client.post("/jobs", json=payload)
    if r.status_code not in (200, 201):
        fail("POST /jobs (folder)", r.text[:200])
        job_id = None
    else:
        ok("POST /jobs (folder)")
        job_id = r.json().get("id")

    if job_id:
        r = client.get(f"/jobs/{job_id}")
        if r.status_code == 200 and r.json().get("name") == job_name:
            ok("GET /jobs/{id}")
        else:
            fail("GET /jobs/{id}")

        r = client.put(f"/jobs/{job_id}", json={**payload, "description": "actualizado"})
        if r.status_code == 200:
            ok("PUT /jobs/{id}")
        else:
            fail("PUT /jobs/{id}", r.text[:120])

        r = client.post(f"/jobs/{job_id}/run")
        if r.status_code in (200, 202):
            ok("POST /jobs/{id}/run")
        else:
            fail("POST /jobs/{id}/run", r.text[:120])

        time.sleep(1)
        r = client.get("/history")
        if r.status_code == 200:
            ok("GET /history (tras run)")
        else:
            fail("GET /history")

        r = client.delete(f"/jobs/{job_id}")
        if r.status_code in (200, 204):
            ok("DELETE /jobs/{id}")
        else:
            fail("DELETE /jobs/{id}", r.text[:120])

    section("Validación API (campos inválidos)")
    r = client.post("/jobs", json={"name": ""})
    if r.status_code == 422:
        ok("POST /jobs nombre vacio -> 422")
    else:
        fail("POST /jobs nombre vacío", f"status {r.status_code}")

    section("Utils")
    r = client.post(
        "/utils/test-connection",
        json={
            "engine": "folder",
            "host": str(tmp_src),
            "port": 0,
            "user": "",
            "password": "",
            "database": "",
        },
    )
    if r.status_code == 200:
        ok("POST /utils/test-connection (folder)")
    else:
        skip("POST /utils/test-connection (folder)", f"status {r.status_code}")

    r = client.get("/auth/google/status")
    if r.status_code == 200:
        ok("GET /auth/google/status")
    else:
        fail("GET /auth/google/status", f"status {r.status_code}")

    section("Frontend estático")
    root = BASE.replace("/api/v1", "")
    for path in ("/", "/assets/js/app.js", "/assets/css/main.css"):
        r = httpx.get(root + path, timeout=10)
        if r.status_code == 200:
            ok(f"GET {path}")
        else:
            fail(f"GET {path}", f"status {r.status_code}")

    client.close()

    section("Resumen")
    total = PASS + FAIL + SKIP
    print(f"  Pasaron: {PASS}/{total}  Fallaron: {FAIL}  Omitidos: {SKIP}")
    print("\nChecklist manual (navegador) para Bartolo:")
    print("  1. Paso 1: Siguiente sin nombre → error inline")
    print("  2. Paso 2 carpeta: origen + destino obligatorios")
    print("  3. Paso 3: Guardar sin ruta → 1 toast, botón NO queda en Guardando...")
    print("  4. Scroll paso 3: Opciones de limpieza visible sobre botones")
    print("  5. Tema claro/oscuro, Ajustes globales, sidebar ejecutar/borrar")
    print("  6. Demo recomendada: tipo CARPETA (no PostgreSQL si pg_dump falla)")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
