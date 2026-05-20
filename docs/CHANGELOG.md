# Changelog — SolbaBackups

## [3.0] — 2026-05-20

### UX / Frontend
- Wizard de 3 pasos con tarjetas de tipo de tarea (BD, Carpeta, Espejo).
- Contraseña en modo edición: UI "Contraseña configurada" + ojo mostrar/ocultar; no se envía `db_password` vacío al guardar.
- Programación con desplegables (hora, minutos, día del mes) en hora peninsular (España).
- Historial y logs con timestamps en `Europe/Madrid`.
- Explorador local: botón "Crear carpeta".
- i18n ES/EN ampliado.

### Backend
- Backup multi-BD: un solo ZIP y una sola subida por ejecución.
- Limpieza de temporales solo bajo `%TEMP%`, nunca `dest_local_path`.
- `POST /utils/test-db` y `/test-connection` con `job_id` opcional para reutilizar contraseña guardada.
- Google Drive: retención por **días** (no por número de archivos); `upload()` solo añade archivos.
- PostgreSQL: autodetección de `pg_dump` en Windows.
- `JobScheduler` (APScheduler) implementado para tests y uso futuro.
- Programación en producción vía **Windows Task Scheduler** (`schtasks`).

### Tests
- 71 tests passing (pytest).
- Script `scripts/smoke_demo_bartolo.py` para smoke E2E con servidor en marcha.

### Limpieza
- Eliminados componentes JS legacy (`assets/js/components/*`) no referenciados por `index.html`.
- BD de test y artefactos SQLite añadidos a `.gitignore`.
