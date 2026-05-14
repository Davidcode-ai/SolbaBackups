<div align="center">

<img src="src/frontend/assets/logo_solba.png" alt="SolbaBackups Logo" width="90"/>

# SolbaBackups

**Sistema de Backups Automáticos Multi-motor con Panel Web**

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![APScheduler](https://img.shields.io/badge/APScheduler-3.x-FF6F00?style=for-the-badge&logo=clockify&logoColor=white)](https://apscheduler.readthedocs.io/)
[![Google Drive](https://img.shields.io/badge/Google%20Drive-API-4285F4?style=for-the-badge&logo=google-drive&logoColor=white)](https://developers.google.com/drive)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-83%20passing-22C55E?style=for-the-badge&logo=pytest&logoColor=white)](tests/)

</div>

---

## ¿Qué es SolbaBackups?

**SolbaBackups** es una aplicación de escritorio y servidor todo-en-uno para la gestión automatizada de copias de seguridad empresariales. Diseñada para funcionar sin conocimientos técnicos avanzados, permite a cualquier administrador configurar, programar y monitorizar backups de múltiples bases de datos y carpetas desde un panel web moderno.

> Concebido para PYMES y departamentos IT que necesitan una solución robusta, auditable y sin costes de licencia.

---

## ✨ Características Principales

| Característica | Descripción |
|---|---|
| 🗄️ **Multi-motor** | PostgreSQL, MySQL/MariaDB, Microsoft SQL Server, SQLite, Access (.mdb) y carpetas |
| ☁️ **Google Drive** | Subida asíncrona con soporte resumible, gestión de carpetas y cuotas |
| 📱 **WhatsApp** | Alertas instantáneas vía WhatsApp Business API ante fallos críticos |
| 📧 **Email SMTP** | Reportes automáticos con logs adjuntos (Gmail, Outlook, cualquier SMTP) |
| 🔍 **Autodiscovery** | Detecta automáticamente las instancias de BD instaladas en el sistema |
| 🕰️ **Programación avanzada** | Cron, diario, semanal, mensual o por intervalo (APScheduler) |
| 🗑️ **Garbage Collector** | Purga automática de backups antiguos, configurable por Job o globalmente |
| 🔒 **Compresión y Cifrado** | ZIP nativo con soporte modular para encriptación AES |
| 📊 **Panel Web** | Dashboard dark/light mode, historial en tiempo real, explorador de archivos |
| 🌍 **Bilingüe** | Interfaz completa en Español e Inglés (i18n dinámico) |
| ♻️ **Restauración** | Restaura cualquier backup exitoso con un solo clic desde el historial |
| 🧪 **Test Suite** | 83 tests automatizados con pytest (cobertura del 46%) |

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                         Dashboard Web                           │
│              (Vanilla JS + HTML5 + Tailwind CSS)                │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP / REST API
┌────────────────────────▼────────────────────────────────────────┐
│                      FastAPI Server                             │
│  /api/v1/jobs   /api/v1/history   /api/v1/settings             │
│  /api/v1/utils  /api/v1/auth      /api/v1/discovery            │
└──────┬──────────────────┬──────────────────────────────────────-┘
       │                  │
┌──────▼──────┐   ┌───────▼───────────────────────────────────────┐
│  APScheduler│   │              Job Pipeline (Core)              │
│  (Cron/     │──▶│  Extractor → Compresor → Destino → Notifier   │
│  Interval)  │   └──┬────────────────────────────┬──────────────-┘
└─────────────┘      │                            │
                ┌────▼────────┐           ┌───────▼──────────┐
                │  Conectores  │           │    Destinos       │
                │  PostgreSQL  │           │  Local / GDrive   │
                │  MySQL       │           └──────────────────┘
                │  SQL Server  │
                │  SQLite/MDB  │
                └─────────────┘
                      │
              ┌───────▼──────────┐
              │  SQLite (local)   │
              │  (SQLAlchemy ORM) │
              └──────────────────┘
```

---

## 🚀 Guía de Instalación Rápida

### Requisitos Previos

- **Python 3.12+** ([descargar](https://www.python.org/downloads/))
- **pip** actualizado: `python -m pip install --upgrade pip`
- *(Opcional)* `pg_dump` / `mysqldump` / `sqlcmd` para los respectivos motores de BD

### 1. Clonar el Repositorio

```bash
git clone https://github.com/Davidcode-ai/SolbaBackups.git
cd SolbaBackups
```

### 2. Crear y Activar Entorno Virtual

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno *(opcional)*

Copia el archivo de ejemplo y edítalo:
```bash
cp .env.example .env
```

Variables disponibles en `.env.example`:

```env
SOLBA_DB_PATH=solba_data.sqlite3   # Ruta de la BD interna
SOLBA_PORT=8000                     # Puerto del servidor web
SOLBA_SECRET_KEY=cambia_esto        # Clave secreta para sesiones
```

### 5. Arrancar el Servidor

```bash
python solba_web.py
```

Abre en tu navegador: 👉 **[http://localhost:8000](http://localhost:8000)**

### 6. Ejecutar los Tests *(para desarrolladores)*

```bash
pip install pytest pytest-asyncio pytest-mock pytest-cov httpx
python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## 📁 Estructura del Proyecto

```
SolbaBackup/
├── src/
│   ├── api/
│   │   └── routers/          # Endpoints FastAPI (jobs, history, settings, utils, auth)
│   ├── connectors/           # Conectores de BD (PostgreSQL, MySQL, SQLServer, SQLite)
│   ├── core/
│   │   ├── job_manager.py    # Orquestador del pipeline de backup
│   │   ├── job_scheduler.py  # Gestión de programación con APScheduler
│   │   ├── cleaner.py        # Garbage Collector (retención de backups)
│   │   └── models.py         # Modelos Pydantic de la API
│   ├── db/
│   │   ├── models.py         # Modelos SQLAlchemy (Job, RunHistory, LogEntry)
│   │   ├── crud.py           # Operaciones CRUD sobre la BD
│   │   └── database.py       # Configuración de sesión SQLAlchemy
│   ├── destinations/         # Destinos (local, Google Drive)
│   ├── notifications/        # Notificadores (email SMTP, WhatsApp)
│   ├── processors/           # Compresor ZIP, Encriptador AES
│   └── frontend/
│       ├── index.html        # Dashboard web principal
│       └── assets/
│           ├── js/app.js     # Lógica JS completa (i18n, API, UI)
│           └── css/          # Estilos CSS
├── tests/
│   ├── conftest.py           # Fixtures compartidos (BD de test aislada)
│   ├── test_api_routers.py   # Tests de endpoints HTTP
│   ├── test_crud.py          # Tests de operaciones de BD
│   ├── test_connectors.py    # Tests de conectores (mocks)
│   ├── test_scheduler_and_cleaner.py
│   └── test_integrations.py  # Tests de Google Drive y WhatsApp
├── requirements.txt
├── requirements_web.txt
├── solba_web.py              # Punto de entrada principal
└── .env.example
```

---

## 🔧 Tecnologías Utilizadas

| Capa | Tecnología | Versión |
|---|---|---|
| Backend | FastAPI | 0.111+ |
| ORM | SQLAlchemy | 2.0 |
| BD Interna | SQLite | 3 |
| Scheduler | APScheduler | 3.x |
| Nube | Google Drive API v3 | — |
| Email | smtplib (stdlib) | — |
| WhatsApp | WhatsApp Business HTTP API | — |
| Frontend | Vanilla JS + HTML5 | — |
| Estilos | Tailwind CSS (CDN) | 3.x |
| Iconos | Font Awesome | 6.x |
| Empaquetado | PyInstaller | 6.x |
| Tests | pytest + pytest-cov | 8.x |

---

## 📸 Capturas de Pantalla

> El panel de control cuenta con modo oscuro nativo, explorador de archivos integrado, historial en tiempo real y un terminal de logs embebido.

---

## 🔐 Seguridad

- Las contraseñas de BD **nunca se sobreescriben** si se envía un campo vacío en la actualización de un Job.
- Las credenciales se almacenan encriptadas en la BD SQLite local (no en texto plano en ficheros de configuración).
- La API dispone de autenticación básica configurable a través de los ajustes globales.

---

## 🤝 Equipo de Desarrollo

Este proyecto ha sido desarrollado como proyecto de prácticas empresariales:

| Rol | Nombre |
|---|---|
| 🏗️ Arquitectura & Backend | Alejandro (ale) |
| 🎨 Frontend & UX | Alejandro (ale) |
| 🔌 Conectores & Integraciones | Alejandro (ale) |
| 🧪 QA & Testing | Alejandro (ale) |
| 👔 Supervisión del Proyecto | Bartolomé |

> Proyecto desarrollado con metodología ágil e integración continua. Suite de tests automatizados garantizan la estabilidad de cada entrega.

---

## 📄 Licencia

Distribuido bajo licencia **MIT**. Consulta el archivo `LICENSE` para más detalles.

---

<div align="center">
  <sub>Hecho con ❤️ y mucho café ☕ por el equipo de prácticas de SolbaBackups</sub>
</div>
