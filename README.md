<div align="center">
  <img src="src/frontend/assets/logo_solba.png" alt="SolbaBackups Logo" width="250" />
</div>

# SolbaBackups

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

**Copias de seguridad empresariales con panel web, programación nativa en Windows y destinos local / Google Drive.**

[Descripción](#descripcion) · [Novedades v3](#novedades-v3) · [Instalación](#instalacion) · [Uso](#uso) · [API](#api) · [Tests](#tests) · [Estructura](#estructura) · [Seguridad](#seguridad)

---

<a id="descripcion"></a>
## Descripción

**SolbaBackups** protege bases de datos y carpetas mediante un pipeline automatizado: volcado → compresión (opcional) → subida → retención → notificaciones. La interfaz web guía al usuario sin exponer detalles técnicos (cron, rutas de `pg_dump`, etc.).

<a id="novedades-v3"></a>
## Novedades v3 (2026)

| Área | Mejora |
|------|--------|
| **UX** | Wizard 3 pasos, tarjetas de tipo de tarea, desplegables de hora (España), contraseña segura en edición |
| **Multi-BD** | Varias BDs en `db_name` (comas) → **un solo ZIP** y **una subida** |
| **Drive** | Retención por días; no borra copias al cambiar formato; subida solo añade archivos |
| **Edición** | Probar / Listar BDs sin reescribir contraseña (`job_id` en API) |
| **PostgreSQL** | Autodetección de `pg_dump.exe` en Windows |
| **Limpieza** | Temporales solo en `%TEMP%`; nunca toca la carpeta destino del usuario |

Detalle completo: [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

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
├── tests/                       # pytest (71+ tests)
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

<a id="instalacion"></a>
## Instalación (desarrollo)

```bash
git clone https://github.com/Davidcode-ai/SolbaBackups.git
cd SolbaBackups
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements_web.txt
copy .env.example .env          # Editar SMTP, etc.
python solba_web.py
```

Abrir: **http://localhost:8765**

### Variables de entorno (`.env`)

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
# Suite completa (BD de test aislada)
python -m pytest tests/ -q

# Smoke con servidor en marcha (otra terminal: python solba_web.py)
python scripts/smoke_demo_bartolo.py
```

Estado esperado: **71 passed**, 12 skipped (tests async sin `pytest-asyncio`).

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

## Microservicio WhatsApp

La carpeta [`ApiWhatsApp/`](ApiWhatsApp/) contiene la API desacoplada desplegada en Render (no forma parte del runtime de `solba_web.py`). Ver su `README.md` local.

---

## Equipo

| Rol | Nombre |
|-----|--------|
| Arquitectura y backend | David |
| Frontend y UX | Alejandro |
| Conectores e integraciones | Manuel |
| QA | Equipo Solba |

---

## Licencia

MIT — ver [`LICENSE`](LICENSE).

---

<div align="center">
  <em>SolbaBackups — Protegiendo sus datos, automatizando su tranquilidad.</em>
</div>
