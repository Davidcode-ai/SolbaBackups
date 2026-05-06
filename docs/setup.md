# Guía de instalación y configuración

## Requisitos previos

| Herramienta | Versión mínima | Notas |
|-------------|---------------|-------|
| Python      | 3.10          | Requerido |
| pip         | 23+           | Incluido con Python |
| pg_dump / psql | cualquiera | Solo para PostgreSQL |
| mysqldump / mysql | cualquiera | Solo para MySQL/MariaDB |
| sqlcmd      | cualquiera    | Solo para SQL Server |
| nmap        | cualquiera    | Opcional, para detección avanzada |

---

## 1. Clonar el repositorio

```bash
git clone https://github.com/vecinoconil/SolbaBackups.git
cd SolbaBackups
```

---

## 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

---

## 3. Abrir el workspace en VSCode

Abre el archivo `SolbaBackups.code-workspace` directamente desde VSCode:

```bash
code SolbaBackups.code-workspace
```

O desde el menú: **Archivo → Abrir área de trabajo desde archivo…**

Se recomienda instalar las extensiones sugeridas cuando VSCode lo proponga.

---

## 4. Configuración básica

Copia el archivo de ejemplo y edítalo:

```bash
cp config.example.yaml config.yaml
```

Edita `config.yaml` con tus valores:

```yaml
backup_dir: "./backups"
log_level: "INFO"          # DEBUG | INFO | WARNING | ERROR
compression: "zip"         # zip | tar.gz | none
retention_days: 30

databases:
  - type: sqlite
    db_path: "/ruta/a/mi/base.db"

  - type: postgresql
    host: "localhost"
    port: 5432
    database: "mi_bd"
    user: "postgres"
    password: "mi_password"

  - type: mysql
    host: "localhost"
    database: "mi_bd"
    user: "root"
    password: "mi_password"

  - type: mdb
    db_path: "/ruta/a/mi/archivo.mdb"

folders:
  - source_dir: "/ruta/a/carpeta_importante"
    incremental: false

google_drive:
  enabled: false
  credentials_file: "credentials.json"
  folder_id: ""            # ID de la carpeta raíz en Drive

sync:
  enabled: false
  pairs:
    - source: "/ruta/origen"
      destination: "/ruta/destino"

schedules:
  - name: "backup_diario_sqlite"
    frequency: "daily"
    at_time: "02:00"
    type: sqlite
    db_path: "/ruta/a/mi/base.db"
```

---

## 5. Configurar Google Drive (opcional)

1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un proyecto y habilita la **Google Drive API**.
3. Crea credenciales OAuth 2.0 de tipo "Aplicación de escritorio".
4. Descarga el archivo `credentials.json` y colócalo en la raíz del proyecto.
5. La primera vez que uses el comando `upload`, se abrirá el navegador para
   autorizarte. El token se guardará en `token.json`.

---

## 6. Variables de entorno

Puedes sobreescribir cualquier ajuste con variables de entorno prefijadas
con `SOLBA_`:

| Variable                | Descripción                        |
|-------------------------|------------------------------------|
| `SOLBA_BACKUP_DIR`      | Directorio de backups              |
| `SOLBA_LOG_LEVEL`       | Nivel de log (INFO, DEBUG…)        |
| `SOLBA_COMPRESSION`     | Método de compresión               |
| `SOLBA_RETENTION_DAYS`  | Días de retención                  |
| `SOLBA_GDRIVE_ENABLED`  | Activar Google Drive (true/false)  |
| `SOLBA_GDRIVE_FOLDER_ID`| ID de carpeta de Google Drive      |

Crea un archivo `.env` en la raíz del proyecto con el formato `CLAVE=valor`.

---

## 7. Ejecutar los tests

```bash
pytest tests/ -v
# Con cobertura:
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## 8. Verificar instalación

```bash
python -m src.main --version
python -m src.main status
```
