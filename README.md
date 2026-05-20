<div align="center">
  <img src="src/frontend/assets/logo_solba.png" alt="SolbaBackups Logo" width="250" />
</div>

# SolbaBackups v3.0

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

**Enterprise-grade backups for Windows teams** — web dashboard, native **Task Scheduler** integration, and **local or Google Drive** destinations. *SolbaBackups v3.0* runs a predictable pipeline (dump or mirror → optional ZIP → upload → retention → **HTML or console reports**) while hiding operational noise (`pg_dump` paths, cron syntax, Drive API details).

[Vista rápida (ES)](#descripcion) · [Key features](#key-features) · [Install & run](#install--run) · [End-user workflow](#uso) · [API](#api) · [Tests](#tests) · [Project layout](#estructura) · [Security](#seguridad)

---

<a id="descripcion"></a>
## Vista rápida (ES)

**SolbaBackups** protege bases de datos y carpetas con un flujo guiado: volcado o espejo → compresión opcional → destino → retención → notificaciones. El panel web está disponible en **español e inglés**.

<a id="key-features"></a>
## Key features

| Capability | What you get |
|------------|----------------|
| **Database auto-discovery** | Detected engines and connection cards in the wizard; SQLite / file engines alongside PostgreSQL, MySQL, and SQL Server. |
| **True-sync mirror** | Folder jobs with **1:1 mirror** (no ZIP) to a local path, with safe destination-root semantics and job-name path normalization. |
| **Notifications** | **Corporate HTML email** (inline CSS, escaped content) plus plain-text fallback; optional **WhatsApp** via the bundled [`ApiWhatsApp/`](ApiWhatsApp/) outbox service. |
| **Corporate UI** | Dark/light dashboard, guided job creation, history with logs, retention preview, and schedule status tied to Windows tasks. |
| **Multi-database export** | Comma-separated `db_name` values produce **one ZIP** and **one upload** per run where applicable. |

Release history: [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

---

<a id="novedades-v3"></a>
## Highlights in v3.0

| Area | Improvement |
|------|-------------|
| **UX** | Three-step wizard, job-type cards, schedule dropdowns (Spain local time hints), secure password handling on edit |
| **Drive** | Day-based retention; additive uploads; safer cleanup semantics |
| **PostgreSQL** | Typical Windows `pg_dump.exe` auto-detection |
| **Safety** | Staging and restore temp files under **`%TEMP%`** only — never the user’s backup destination tree |

---

<a id="estructura"></a>
## Estructura del proyecto

```text
BackUp-Solba/
├── solba_web.py                 # Entrada: uvicorn en :8765
├── src/
│   ├── api/
│   │   ├── server.py            # FastAPI + estáticos + lifespan
│   │   └── routers/             # jobs, history, settings, utils, auth, stats, logs
│   ├── core/
│   │   ├── job_manager.py       # Pipeline de backup (orquestador)
│   │   ├── job_runner.py        # Ejecución en background
│   │   ├── db_credentials.py    # Resolución segura de contraseñas
│   │   ├── cleaner.py           # Garbage collector / retención global
│   │   ├── windows_tasks.py     # Programación schtasks (producción)
│   │   └── models.py            # Esquemas Pydantic API
│   ├── connectors/              # postgresql, mysql, sqlserver, sqlite
│   ├── destinations/            # local.py, google_drive.py
│   ├── processors/              # compressor, encryptor
│   ├── db/                      # SQLAlchemy + SQLite interna
│   ├── scheduler/
│   │   └── job_scheduler.py     # APScheduler (tests / alternativo)
│   └── frontend/
│       ├── index.html
│       └── assets/js/
│           ├── app.js           # UI principal (wizard, i18n, historial)
│           └── api.js           # Cliente REST
├── tests/                       # pytest (~98 tests, see CI / local run)
├── scripts/
│   └── smoke_demo_bartolo.py    # Smoke E2E (servidor en marcha)
├── ApiWhatsApp/                 # Microservicio WhatsApp (Render) — independiente
├── docs/
│   ├── CHANGELOG.md
│   └── architecture.md
├── requirements.txt
├── requirements_web.txt
└── .env.example
```

**Nota:** Los módulos `src/backup/`, `src/storage/` y `src/ui/cli.py` son rutas **legacy** (CLI antigua). El flujo activo es `solba_web.py` → `job_manager.py`.

---

<a id="install--run"></a>
<a id="instalacion"></a>
## Install & run (development)

```bash
git clone https://github.com/Davidcode-ai/SolbaBackups.git
cd SolbaBackups
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements_web.txt
copy .env.example .env          # Edit SMTP and options
python solba_web.py
```

Open **http://localhost:8765**. Switch language under **Global Settings** (ES / EN).

### Environment (`.env`)

| Variable | Uso |
|----------|-----|
| `SOLBA_SMTP_*` | Notificaciones por email |
| `SOLBA_ENCRYPTION` / clave en `config.yaml` | Cifrado de campos sensibles en BD |

Google Drive: `credentials.json` + `token.json` en la raíz del proyecto (ver [Configuración](#configuracion)).

---

<a id="configuracion"></a>
## Configuración

- **Google Drive:** OAuth desde Ajustes globales; backups en carpeta por nombre de tarea.
- **Retención:** `0` = no borrar nunca; `N` = borrar copias con más de N **días** (local y Drive).
- **Programación:** Diario / Semanal / Mensual con desplegables; internamente se genera cron y se registra en **Programador de tareas de Windows**.
- **PostgreSQL:** Instalar cliente PostgreSQL (incluye `pg_dump`) o dejar que la app lo detecte en rutas típicas de Windows.

---

<a id="uso"></a>
## Uso

### Panel web
1. **Nueva tarea** → elegir tipo (BD / Carpeta / Espejo).
2. Origen, destino (local o Drive), programación y retención.
3. **Guardar** y **Ejecutar** desde la barra lateral.

### Tipos de tarea

| Tipo | `db_type` | Comportamiento |
|------|-----------|----------------|
| Base de datos | `postgresql`, `mysql`, … | Volcado + ZIP opcional |
| Carpeta | `folder` | Sincronización incremental + ZIP |
| Espejo | `sync` | Copia 1:1 sin compresión (solo local) |

### Múltiples bases de datos
En el campo de base de datos, separar por comas: `app_db,logs_db`. Se genera **un único** archivo comprimido por ejecución.

### Línea de comandos (servicio)

```bash
python solba_web.py
# o binario empaquetado:
SolbaBackups.exe
```

---

<a id="api"></a>
## API REST (resumen)

Prefijo: `/api/v1`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/jobs` | Listar tareas |
| POST | `/jobs` | Crear tarea |
| PUT | `/jobs/{id}` | Actualizar (password vacío = no cambiar) |
| POST | `/jobs/{id}/run` | Ejecutar ahora |
| GET | `/history` | Historial de ejecuciones |
| POST | `/utils/test-connection` | Probar conexión (`job_id` opcional) |
| POST | `/utils/test-db` | Listar BDs (`job_id` opcional) |
| POST | `/utils/create-local-dir` | Crear carpeta en explorador |
| GET | `/docs` | Swagger OpenAPI |

---

<a id="tests"></a>
## Tests

```bash
python -m pytest tests/ -q
```

Expected: **98 passed** (warnings from SQLAlchemy/pytest-asyncio may appear depending on Python version).

Smoke (server running in another terminal: `python solba_web.py`):

```bash
python scripts/smoke_demo_bartolo.py
```

---

<a id="seguridad"></a>
## Seguridad

- Las contraseñas **no se devuelven** en `GET /jobs`.
- En `PUT`, `db_password` vacío u omitido **no sobrescribe** la existente.
- En edición, test de conexión usa `job_id` sin enviar la contraseña por red de nuevo.
- `credentials.json`, `token.json` y `.env` están en `.gitignore`.
- Contraseñas en BD: texto plano (MVP) o `db_password_enc` con Fernet si hay `encryption_key`.

---

## Stack tecnológico

| Capa | Tecnología |
|------|------------|
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2 |
| BD app | SQLite |
| Scheduler prod. | Windows Task Scheduler |
| Scheduler alt. | APScheduler 3 |
| Frontend | HTML + Tailwind (CDN) + Vanilla JS |
| Nube | Google Drive API v3 |
| Tests | pytest |

---

## WhatsApp microservice (`ApiWhatsApp/`)

The [`ApiWhatsApp/`](ApiWhatsApp/) folder ships a **standalone** FastAPI + outbox worker for Meta / WAHA delivery. It is **not** imported by `solba_web.py`; SolbaBackups optionally POSTs backup status events when that service is configured. See **[ApiWhatsApp/README.md](ApiWhatsApp/README.md)** for deploy and env vars.

---

## Equipo

| Rol | Nombre |
|-----|--------|
| Arquitectura y backend | David |
| Frontend y UX | Alejandro |
| Conectores e integraciones | Manuel |
| QA | Equipo Solba |

---

## Instalador Windows

Generar el `.exe` de instalación (como en [Releases](https://github.com/Davidcode-ai/SolbaBackups/releases)):

```powershell
.\scripts\build_installer.ps1
```

Resultado: `Output\SolbaSetup-3.0.0.exe`. Guía detallada: [`docs/BUILD_INSTALLER.md`](docs/BUILD_INSTALLER.md).

---

## Licencia

MIT — ver [`LICENSE`](LICENSE).

---

<div align="center">
  <em>SolbaBackups — Protegiendo sus datos, automatizando su tranquilidad.</em>
</div>
