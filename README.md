# SolbaBackups

**Gestor de copias de seguridad de bases de datos y carpetas de ficheros**

> Proyecto de prácticas colaborativo – 3 alumnos

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## ✨ Características

| Funcionalidad | Descripción |
|---------------|-------------|
| 🗄️ **Bases de datos** | SQLite, PostgreSQL, MySQL/MariaDB, SQL Server, MDB/Access |
| 📅 **Planificación** | Diaria, semanal, mensual, días concretos de la semana |
| ☁️ **Google Drive** | Subida automática organizada por mes |
| 🔄 **Sincronización** | Mirror, actualización y monitorización en tiempo real |
| 🔍 **Detección** | Escaneo de puertos TCP y archivos locales |
| ♻️ **Restauración** | Restaura cualquier tipo de backup con un comando |
| 💾 **Compresión** | ZIP, TAR.GZ o sin compresión |
| 🗑️ **Retención** | Purga automática de copias antiguas |

---

## 🚀 Inicio rápido

```bash
# 1. Clonar y configurar
git clone https://github.com/vecinoconil/SolbaBackups.git
cd SolbaBackups
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configurar (editar config.yaml según tus necesidades)
cp config.example.yaml config.yaml

# 3. Abrir en VSCode
code SolbaBackups.code-workspace

# 4. Realizar tu primera copia de seguridad
python -m src.main backup sqlite --db /ruta/a/mi.db
python -m src.main status
```

---

## 📦 Comandos principales

```bash
# Copias de seguridad
python -m src.main backup sqlite     --db /ruta/mi.db
python -m src.main backup postgresql --host localhost --db mibd --user postgres
python -m src.main backup mysql      --host localhost --db mibd --user root
python -m src.main backup sqlserver  --host 192.168.1.10 --db mibd --user sa
python -m src.main backup mdb        --db /ruta/datos.mdb
python -m src.main backup folder     --source /mi/carpeta --incremental

# Restauración
python -m src.main restore sqlite --backup backups/sqlite_mi_20250101.zip --target /nueva/mi.db
python -m src.main restore folder --backup backups/folder_docs.zip --target /docs_restaurados

# Detección de BD en una máquina
python -m src.main detect --host 192.168.1.100
python -m src.main detect --local --search-dir /home/usuario

# Sincronización de carpetas
python -m src.main sync --source /origen --dest /destino --mode mirror
python -m src.main sync --source /origen --dest /destino --mode watch

# Subir a Google Drive
python -m src.main upload --file backups/mi_backup.zip

# Ver estado de backups locales
python -m src.main status
```

---

## 📁 Estructura del proyecto

```
SolbaBackups/
├── SolbaBackups.code-workspace   ← Workspace de VSCode
├── config.example.yaml           ← Plantilla de configuración
├── requirements.txt
├── src/
│   ├── backup/         ← Proveedores de backup (SQLite, PG, MySQL, etc.)
│   ├── scheduler/      ← Planificador de tareas
│   ├── storage/        ← Almacenamiento local + Google Drive
│   ├── sync/           ← Sincronización de carpetas
│   ├── detector/       ← Detección de BD en red y archivos
│   ├── restore/        ← Restauración de backups
│   └── ui/             ← Interfaz CLI (Click)
├── tests/              ← Tests unitarios (pytest)
└── docs/
    ├── architecture.md
    ├── setup.md
    ├── usage.md
    └── contributing.md
```

---

## 🧪 Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## 📖 Documentación

| Documento | Descripción |
|-----------|-------------|
| [Arquitectura](docs/architecture.md) | Diseño del sistema y decisiones técnicas |
| [Instalación](docs/setup.md) | Guía de instalación y configuración |
| [Uso](docs/usage.md) | Manual completo de todos los comandos |
| [Contribución](docs/contributing.md) | Flujo de trabajo y estándares de código |

---

## 🤝 Colaboradores

Proyecto de prácticas desarrollado por 3 alumnos. Ver [docs/contributing.md](docs/contributing.md)
para el flujo de trabajo con Git y la distribución de responsabilidades.

---

## 📄 Licencia

MIT License
