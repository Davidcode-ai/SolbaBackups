# Arquitectura de SolbaBackups

## Visión General

SolbaBackups es un sistema modular de copias de seguridad para bases de datos
y carpetas de ficheros, desarrollado en Python. A continuación se describe la
arquitectura y la responsabilidad de cada módulo.

```
SolbaBackups/
├── src/
│   ├── main.py              ← Punto de entrada
│   ├── config/
│   │   └── settings.py      ← Configuración (YAML + variables de entorno)
│   ├── backup/
│   │   ├── base.py          ← Clase abstracta BaseBackup + BackupResult
│   │   ├── sqlite_backup.py ← Proveedor SQLite
│   │   ├── postgresql_backup.py ← Proveedor PostgreSQL (pg_dump)
│   │   ├── sql_backup.py    ← Proveedores MySQL y SQL Server
│   │   ├── mdb_backup.py    ← Proveedor MDB/Access
│   │   └── folder_backup.py ← Proveedor de carpetas de ficheros
│   ├── scheduler/
│   │   └── scheduler.py     ← Planificador (diario, semanal, mensual, etc.)
│   ├── storage/
│   │   ├── local_storage.py ← Gestión de backups locales
│   │   └── google_drive.py  ← Subida / listado en Google Drive
│   ├── sync/
│   │   └── folder_sync.py   ← Sincronización de carpetas (mirror/update/watch)
│   ├── detector/
│   │   └── db_detector.py   ← Detección de BD en red y en archivos locales
│   ├── restore/
│   │   └── restore_manager.py ← Restauración de todos los tipos de backup
│   └── ui/
│       └── cli.py           ← Interfaz de línea de comandos (Click)
├── tests/                   ← Tests unitarios (pytest)
└── docs/                    ← Documentación
```

---

## Capas del sistema

### 1. Capa de configuración (`src/config/`)

La clase `Settings` carga la configuración en orden de precedencia:

1. Valores por defecto (hardcoded en `_DEFAULTS`).
2. Archivo `config.yaml` en la raíz del proyecto.
3. Variables de entorno con prefijo `SOLBA_` (mayor prioridad).

El archivo `config.yaml` soporta toda la configuración del sistema:
bases de datos, carpetas, programaciones, credenciales de Google Drive, etc.

### 2. Capa de copia de seguridad (`src/backup/`)

Todos los proveedores heredan de `BaseBackup` (patrón Template Method):

- **`_do_backup(timestamp, **kwargs)`** → genera el archivo raw.
- **`_source_label(**kwargs)`** → etiqueta para logs.
- **`_compress(raw_path)`** → comprime en ZIP, TAR.GZ o sin compresión.
- **`purge_old_backups(prefix, retention_days)`** → elimina copias antiguas.

El resultado siempre es un objeto `BackupResult` con `success`, `destination`,
`size_bytes` y `error`.

### 3. Capa de planificación (`src/scheduler/`)

`ScheduledJob` encapsula una tarea con su frecuencia y la registra en la
librería `schedule`. `BackupScheduler` gestiona el ciclo de vida:
añadir, eliminar y ejecutar tareas en un hilo daemon opcional.

Frecuencias soportadas: `daily`, `weekly`, `monthly`, `weekdays`, `interval`.

### 4. Capa de almacenamiento (`src/storage/`)

- **`LocalStorage`**: lista, purga y calcula el uso de disco del directorio
  de backups.
- **`GoogleDriveUploader`**: gestiona la autenticación OAuth2 y sube archivos
  organizándolos en subcarpetas por mes (`YYYY-MM`).

### 5. Capa de sincronización (`src/sync/`)

`FolderSync` soporta tres modos:

| Modo     | Comportamiento                                        |
|----------|-------------------------------------------------------|
| `update` | Copia archivos nuevos o más recientes hacia destino.  |
| `mirror` | Como `update`, pero además elimina lo que no existe en origen. |
| `watch`  | Monitoriza cambios en tiempo real con `watchdog`.     |

### 6. Capa de detección (`src/detector/`)

`DatabaseDetector` localiza servicios de BD mediante:

- **Sondeo TCP** (`socket`): rápido y sin dependencias extra.
- **nmap** (opcional): más detallado, detecta versiones.
- **Archivos locales**: busca `.db`, `.sqlite`, `.mdb`, `.accdb`.

### 7. Capa de restauración (`src/restore/`)

`RestoreManager` orquesta la restauración de cada tipo de backup:

| Tipo        | Herramienta        |
|-------------|-------------------|
| SQLite      | API `sqlite3.backup()` |
| PostgreSQL  | `psql` / `pg_restore` |
| MySQL       | `mysql` client     |
| SQL Server  | `sqlcmd`           |
| MDB         | `shutil.copy2`     |
| Carpeta     | `zipfile` / `tarfile` / `shutil` |

### 8. Interfaz de usuario (`src/ui/`)

CLI construida con `Click`. Los comandos principales son:

```
python -m src.main backup   sqlite|postgresql|mysql|sqlserver|mdb|folder
python -m src.main restore  sqlite|postgresql|mysql|folder
python -m src.main detect   --host <ip>
python -m src.main sync     --source <dir> --dest <dir>
python -m src.main upload   --file <path>
python -m src.main status
```

---

## Flujo típico de uso

```
Usuario → CLI (click)
            ↓
        Settings (config.yaml / env)
            ↓
        BackupProvider._do_backup()   →  archivo raw
            ↓
        BaseBackup._compress()        →  ZIP / TAR.GZ
            ↓
        LocalStorage                  →  directorio backups/
            ↓ (opcional)
        GoogleDriveUploader           →  Google Drive
            ↓ (opcional)
        BackupScheduler               →  ejecución periódica
```

---

## Decisiones de diseño

- **Patrón Template Method** en `BaseBackup`: evita duplicar la lógica de
  compresión y registro en cada proveedor.
- **Configuración por capas**: permite a los desarrolladores trabajar con
  valores por defecto y solo sobreescribir lo necesario.
- **Sin dependencias obligatorias de BD**: los drivers de bases de datos son
  opcionales; el sistema funciona con SQLite y carpetas sin instalar nada
  adicional.
- **Testabilidad**: todas las clases reciben sus dependencias por parámetro
  (inyección de dependencias implícita), facilitando el uso de mocks.
