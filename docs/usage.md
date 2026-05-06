# Manual de uso de SolbaBackups

## Inicio rápido

Activa el entorno virtual y ejecuta el sistema:

```bash
source venv/bin/activate
python -m src.main --help
```

---

## Comandos disponibles

### `backup` – Realizar copias de seguridad

#### SQLite

```bash
python -m src.main backup sqlite --db /ruta/a/mi.db
python -m src.main backup sqlite --db /ruta/a/mi.db --compression tar.gz
```

#### PostgreSQL

```bash
python -m src.main backup postgresql \
  --host localhost --port 5432 \
  --db mi_base \
  --user postgres \
  --password mi_password
```

#### MySQL / MariaDB

```bash
python -m src.main backup mysql \
  --host localhost \
  --db mi_base \
  --user root \
  --password mi_password
```

#### SQL Server

```bash
# Con acceso al sistema de archivos del servidor (genera .bak nativo)
python -m src.main backup sqlserver \
  --host 192.168.1.10 \
  --db AdventureWorks \
  --user sa --password Mi_Pass \
  --server-bak-path "C:\SQLBackups"

# Sin acceso (exporta esquema via ODBC)
python -m src.main backup sqlserver \
  --host 192.168.1.10 \
  --db AdventureWorks \
  --user sa --password Mi_Pass
```

#### MDB / Microsoft Access

```bash
python -m src.main backup mdb --db /ruta/a/datos.mdb
python -m src.main backup mdb --db /ruta/a/datos.accdb --password secreto
```

#### Carpeta de ficheros

```bash
# Copia completa
python -m src.main backup folder --source /home/usuario/documentos

# Incremental (solo archivos nuevos o modificados)
python -m src.main backup folder --source /home/usuario/documentos --incremental

# Excluir patrones
python -m src.main backup folder --source /home/usuario/proyecto \
  --exclude "*.pyc" --exclude "__pycache__"
```

---

### `restore` – Restaurar copias de seguridad

#### SQLite

```bash
python -m src.main restore sqlite \
  --backup backups/sqlite_mi_20250101_020000.zip \
  --target /nueva/ruta/mi.db
```

#### PostgreSQL

```bash
python -m src.main restore postgresql \
  --backup backups/pgsql_mi_base_20250101_020000.sql \
  --host localhost --db mi_base \
  --user postgres --password mi_password \
  --create-db         # crea la BD si no existe
```

#### MySQL

```bash
python -m src.main restore mysql \
  --backup backups/mysql_mi_base_20250101.sql.zip \
  --host localhost --db mi_base \
  --user root --password mi_password \
  --create-db
```

#### Carpeta

```bash
python -m src.main restore folder \
  --backup backups/folder_documentos_20250101_020000.zip \
  --target /home/usuario/documentos_restaurados
```

---

### `detect` – Detectar bases de datos

```bash
# Escaneo básico (sondeo TCP)
python -m src.main detect --host 192.168.1.100

# Escaneo con nmap (más detallado)
python -m src.main detect --host 192.168.1.100 --nmap

# Buscar archivos SQLite/MDB en el sistema local
python -m src.main detect --local

# Especificar directorios de búsqueda
python -m src.main detect --local \
  --search-dir /home/usuario \
  --search-dir /var/lib
```

Ejemplo de salida:
```
🔍 Escaneando 192.168.1.100...

📡 Servicios de BD detectados en red:
╭──────────────────┬──────────────────┬────────┬────────╮
│ Base de datos    │ Host             │ Puerto │ Estado │
├──────────────────┼──────────────────┼────────┼────────┤
│ MySQL/MariaDB    │ 192.168.1.100    │ 3306   │ OPEN   │
│ PostgreSQL       │ 192.168.1.100    │ 5432   │ OPEN   │
╰──────────────────┴──────────────────┴────────┴────────╯
```

---

### `sync` – Sincronizar carpetas

```bash
# Actualización unidireccional (solo copia lo nuevo/modificado)
python -m src.main sync \
  --source /origen \
  --dest /destino \
  --mode update

# Espejo (elimina en destino lo que no está en origen)
python -m src.main sync \
  --source /origen \
  --dest /destino \
  --mode mirror

# Monitorización en tiempo real (Ctrl+C para detener)
python -m src.main sync \
  --source /origen \
  --dest /destino \
  --mode watch

# Excluir archivos temporales
python -m src.main sync \
  --source /proyecto \
  --dest /backup/proyecto \
  --exclude "*.tmp" --exclude ".git"
```

---

### `upload` – Subir a Google Drive

```bash
python -m src.main upload \
  --file backups/sqlite_mi_20250101_020000.zip \
  --folder-id 1ABC123xyz       # ID de la carpeta de Drive (opcional)
```

El archivo se sube dentro de una subcarpeta `YYYY-MM` en la carpeta indicada.

---

### `status` – Estado de los backups locales

```bash
python -m src.main status
```

Ejemplo de salida:
```
📁 Directorio de backups: /home/usuario/SolbaBackups/backups
   Archivos: 12  |  Espacio: 45.30 MB

╭──────────────────────────────────────────┬────────────┬─────────────────────╮
│ Nombre                                   │ Tamaño(KB) │ Modificado          │
├──────────────────────────────────────────┼────────────┼─────────────────────┤
│ sqlite_clientes_20250501_020000.zip      │ 234.5      │ 2025-05-01 02:00    │
│ folder_documentos_20250430_020000.zip    │ 1024.0     │ 2025-04-30 02:00    │
╰──────────────────────────────────────────┴────────────┴─────────────────────╯
```

---

## Programación de tareas (Scheduler)

Para ejecutar el planificador en modo continuo, crea un script Python o
configura las tareas en `config.yaml` y lanza el daemon:

```python
# run_scheduler.py
from src.config.settings import settings
from src.scheduler.scheduler import BackupScheduler, ScheduledJob
from src.backup.sqlite_backup import SQLiteBackup
from pathlib import Path

scheduler = BackupScheduler()

def my_backup():
    bk = SQLiteBackup(settings.backup_dir)
    bk.backup(db_path="/ruta/mi.db")

job = ScheduledJob(
    name="backup_nocturno",
    frequency="daily",
    at_time="02:00",
    job_fn=my_backup,
)
scheduler.add_job(job)
scheduler.start(blocking=True)   # Bloquea el proceso
```

```bash
python run_scheduler.py
```

Para ejecutarlo como servicio del sistema, consulta la documentación de
`systemd` (Linux) o el Programador de tareas (Windows).
