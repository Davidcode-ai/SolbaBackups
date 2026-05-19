# 🛡️ PLAN DE REFACTORIZACIÓN ABSOLUTA V3.0 — "A Prueba de Padres"

> **Objetivo:** Que una persona de 54 años, sin conocimientos técnicos, pueda usar SolbaBackups sin dudar ni una sola vez.
>
> **Regla de oro:** Cada elemento de la UI debe ser autoexplicativo. Si hay que pensar, está mal diseñado.

---

## 📋 Resumen Ejecutivo

| Fase | Foco | Archivos Principales | Prioridad |
|------|------|---------------------|-----------|
| **Fase 1** | Rescate Visual y Usabilidad | `index.html`, `app.js`, `main.css` | 🔴 CRÍTICA |
| **Fase 2** | UX de Destinos y Selección | `app.js`, `utils.py`, `jobs.py`, `models.py` | 🟡 ALTA |
| **Fase 3** | Lógica Core y Bugs Backend | `job_manager.py`, `compressor.py` | 🔴 CRÍTICA |

---

## 🔴 FASE 1: Rescate Visual y Usabilidad

> **Impacto:** Frontend puro. Archivos: `src/frontend/index.html`, `src/frontend/assets/js/app.js`, `src/frontend/assets/css/main.css`

### 1.1 — Botones Perdidos (Footer del Formulario)

**Diagnóstico:**
El formulario `#createJobForm` (línea ~809 de `index.html`) tiene su footer con el botón `#btnSaveJob` en la línea ~1097. El formulario está dentro de un contenedor con `overflow-y-auto` (el `<div class="flex-1 overflow-y-auto p-8">` de `<main>`, línea 785). El footer del formulario no tiene posicionamiento fijo (`sticky`) ni está fuera del scroll, por lo que en pantallas pequeñas o con muchos campos visibles, los botones "Guardar"/"Anterior" se van fuera del viewport y el usuario no los ve.

**Plan de Acción:**

- [ ] **1.1.1** — Convertir el footer del formulario (`<div class="pt-4 border-t border-slate-800 flex justify-end gap-3">`, línea 1097) en un footer `sticky` al fondo del contenedor del formulario. Usar `sticky bottom-0 bg-white dark:bg-surface-900 z-10 py-4 -mx-6 px-6` para que siempre sea visible independientemente del scroll.
- [ ] **1.1.2** — Añadir una sombra sutil hacia arriba (`shadow-[0_-4px_12px_rgba(0,0,0,0.1)]`) al footer cuando haya contenido por debajo (scroll), para que el usuario perciba visualmente que los botones están "anclados" y el formulario sigue por debajo.
- [ ] **1.1.3** — Verificar en resoluciones ≤768px que los botones son siempre visibles y accesibles, especialmente cuando se abren los `<details>` de configuración avanzada de red que expanden el formulario.

---

### 1.2 — Bug de los Clones (Botones 'Cancelar' infinitos en modo edición)

**Diagnóstico:**
En `app.js`, función `setFormEditMode()` (línea ~718), se crea un botón `#btnCancelEdit` dinámicamente y se añade al `btnSave.parentElement` con `appendChild`. El guard check es `if (!form.querySelector('#btnCancelEdit'))` (línea 827). **Sin embargo**, el polling de `setupPolling()` (línea 954) llama a `loadJobs(true)` cada 8 segundos, que reconstruye toda la lista de Jobs. Si el usuario hace clic en "Editar" otra vez (o el polling dispara algún re-render del form), la condición del guard puede fallar si hay una race condition o si el DOM fue manipulado entre ciclos.

Además, si el formulario se re-renderiza parcialmente (por ejemplo, si algún evento del Discovery reconstruye la sección), el botón de cancelar podría duplicarse porque `form.querySelector('#btnCancelEdit')` no lo encontraría en el nuevo DOM.

**Plan de Acción:**

- [ ] **1.2.1** — Antes de crear el botón de cancelar, ejecutar siempre una limpieza: `form.querySelectorAll('#btnCancelEdit').forEach(b => b.remove())` para eliminar TODOS los clones previos antes de añadir uno nuevo. Es la solución más defensiva.
- [ ] **1.2.2** — Mover el botón "Cancelar" al HTML estático (en `index.html`, dentro del footer del formulario junto a `#btnSaveJob`) con clase `hidden` por defecto. En `setFormEditMode()` solo hacer `.classList.remove('hidden')` y en `resetFormToCreateMode()` hacer `.classList.add('hidden')`. Esto elimina la creación dinámica de raíz.
- [ ] **1.2.3** — Añadir el listener de clic del botón "Cancelar" en `initJobFormValidation()` de forma estática (usando delegación de eventos sobre el form, que ya existe en la línea 493-497) en lugar de crearlo dinámicamente.

---

### 1.3 — Sidebar Unificada (Eliminar icono de Sincronizar)

**Diagnóstico:**
En `app.js`, función `loadJobs()` (línea ~126-132), cuando `job.last_run_status === 'success'`, el botón de acción cambia de `fa-play` a `fa-sync` (el icono de la "ruedita"). Esto confunde al usuario: ve dos iconos distintos (play y sync) y no entiende qué hace cada uno.

**Plan de Acción:**

- [ ] **1.3.1** — Eliminar la lógica condicional del icono `fa-sync` en `loadJobs()` (líneas 126-132 y 237-243 de `app.js`). El botón de acción debe mostrar SIEMPRE el icono `fa-play` con el title "Ejecutar Backup" independientemente del estado previo.
- [ ] **1.3.2** — En `handleRunJob()` (sección `finally`, líneas 228-243), eliminar igualmente la condición de `lastStatus === 'success'` que cambia el icono a `fa-sync`. Dejar siempre `fa-play`.
- [ ] **1.3.3** — Actualizar las traducciones i18n: la key `btn_sync_changes` ya no se usará. Limpiar la referencia pero sin borrar la key del diccionario por retrocompatibilidad.

---

### 1.4 — Lavado de Cara Premium (Diseño Tailwind limpio)

**Diagnóstico:**
Los inputs del formulario usan estilos mixtos y no hay un sistema de diseño coherente. Algunos inputs usan `bg-slate-50 dark:bg-surface-950` (línea ~821) y otros `bg-white dark:bg-surface-900` (línea ~864). Los `<select>` no tienen el mismo padding que los `<input>`. Las tarjetas de Discovery y el formulario no están alineadas proporcionalmente.

**Plan de Acción:**

- [ ] **1.4.1** — **Unificar estilos de inputs:** Crear una clase base reutilizable (en el bloque `<style>` o mediante Tailwind `@apply` inline) para todos los inputs, selects y textareas del formulario. Propuesta: `bg-white dark:bg-surface-950 border border-slate-300 dark:border-slate-700 rounded-lg p-3 text-sm text-slate-900 dark:text-white focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all`.
- [ ] **1.4.2** — **Proporciones de las tarjetas de Discovery:** Asegurar que todas las tarjetas del grid `#discoveryContainer` (línea ~827) tengan `min-h-[72px]` para que estén alineadas visualmente. Añadir `items-stretch` al contenedor grid.
- [ ] **1.4.3** — **Textos de ayuda coloquiales:** Sustituir los placeholders técnicos por textos que un usuario no técnico entienda:
  - `"Ej: Backup Base de Datos Producción"` → `"Ponle un nombre fácil, ej: Copias del lunes"`
  - `"Ej: 127.0.0.1 o mi-servidor.local"` → `"Dirección del servidor (pregunta a tu informático)"`
  - `"Ej: mi_base_de_datos"` → `"Nombre exacto de tu base de datos"`
  - `"Ej: C:\MisBackups o \\Servidor\Backups"` → `"¿Dónde quieres guardar las copias? Ej: D:\Copias"`
  - Actualizar estas cadenas tanto en `index.html` (los atributos `placeholder`) como en el diccionario i18n de `app.js` (claves `ph_*`).
- [ ] **1.4.4** — **Separadores y espaciado:** Revisar que cada sección del formulario (`Nombre`, `Motores Detectados`, `Config Avanzada de Red`, `Credenciales`, `Ruta origen`, `Destino`, `Retención`, `Footer botones`) tenga un separador visual claro (`border-t`) y un `space-y-6` consistente. Eliminar los `mt-4` ad-hoc que crean inconsistencias.
- [ ] **1.4.5** — **Sidebar izquierda:** Asegurar que el botón "Nuevo Job" (`#btnNewJobSidebar`, línea ~741) resetea el formulario correctamente y hace scroll al top del formulario. Conectar su evento `click` a `resetFormToCreateMode()` + scroll.
- [ ] **1.4.6** — **Labels descriptivos para usuario no técnico:** Añadir subtítulos o texto de ayuda debajo de labels clave. Por ejemplo, bajo "Motor de Base de Datos" añadir: `<p class="text-xs text-slate-400 mt-1">Si no sabes cuál es, elige "Fichero Local"</p>`.

---

## 🟡 FASE 2: UX de Destinos y Selección

> **Impacto:** Frontend + Backend. Archivos: `app.js`, `index.html`, `src/api/routers/utils.py`, `src/api/routers/jobs.py`, `src/core/models.py`, `src/db/models.py`, `src/core/job_manager.py`

### 2.1 — Crear Carpeta en el Explorador Local de Archivos

**Diagnóstico:**
El explorador de archivos web (`openFileExplorer()` / `renderExplorerPath()` en `app.js`, líneas ~2389-2458) permite navegar por carpetas y seleccionar una ruta. Pero NO tiene la opción de crear una carpeta nueva sobre la marcha. Si el usuario quiere guardar backups en una carpeta que aún no existe (ej: `D:\Copias\2024`), tiene que salir de la app, abrir el explorador de Windows, crear la carpeta, y volver a la app. Eso es inaceptable para nuestro usuario objetivo.

La API `GET /api/v1/utils/list-dir` (en `utils.py`, línea ~130) ya devuelve el listado de carpetas/archivos. Solo falta un endpoint `POST /api/v1/utils/create-dir` para crear carpetas y un botón en el modal del explorador.

**Plan de Acción:**

- [ ] **2.1.1** — **Backend:** Crear endpoint `POST /api/v1/utils/create-dir` en `utils.py`:
  ```python
  class CreateDirRequest(BaseModel):
      parent_path: str
      folder_name: str

  @router.post("/create-dir")
  def create_dir(payload: CreateDirRequest):
      # Validar que parent_path existe y es directorio
      # Sanitizar folder_name (prohibir caracteres inválidos: /\:*?"<>|)
      # Crear la carpeta con os.makedirs(full_path, exist_ok=True)
      # Retornar {"success": True, "path": full_path}
  ```
- [ ] **2.1.2** — **Frontend (HTML):** Añadir un botón `📁 Crear nueva carpeta aquí` en el modal `#fileExplorerModal` (en `index.html`), junto a los botones existentes del footer del explorador (`btnExplorerSelect`, `btnExplorerCancel`). Usar un icono de `fa-folder-plus` y estilo coherente con los demás botones del modal.
- [ ] **2.1.3** — **Frontend (JS):** En `app.js`, añadir el handler del botón:
  1. Mostrar un `prompt()` nativo o un input inline pidiendo el nombre de la carpeta nueva.
  2. Llamar a `POST /api/v1/utils/create-dir` con `{ parent_path: currentExplorerPath, folder_name: nombre }`.
  3. Si éxito, refrescar `renderExplorerPath(currentExplorerPath)` para mostrar la carpeta recién creada.
  4. Si error, mostrar `showToast()` con el mensaje del backend.
- [ ] **2.1.4** — Añadir las traducciones i18n necesarias: `btn_create_local_folder`, `prompt_new_folder_name`, `ph_new_folder_name`, `toast_folder_created`, `error_create_folder_local`.

---

### 2.2 — Selección Múltiple de Bases de Datos (Checkboxes)

**Diagnóstico:**
Actualmente, el campo `db_name` en el modelo `JobBase` (en `models.py`, línea ~31) es un `str | None`, es decir, un solo nombre de base de datos. El frontend envía `db_name: "mi_bd"` (string) y el backend hace un volcado de esa única BD.

Para permitir múltiples BDs, necesitamos:
1. Que el frontend envíe un array `db_names: ["bd1", "bd2"]` (o mantener `db_name` como string separado por comas para retrocompatibilidad).
2. Que el backend itere sobre cada BD y ejecute el volcado secuencialmente.
3. Que el formulario del frontend cambie de un `<input type="text">` a checkboxes con las BDs descubiertas o escritas manualmente.

**Plan de Acción:**

- [ ] **2.2.1** — **Modelo Pydantic (`models.py`):** Añadir un campo `db_names: list[str] | None = None` a `JobBase` y `JobUpdate`. Mantener `db_name` por retrocompatibilidad (si `db_names` está vacío, usar `db_name` como fallback con una sola BD).
- [ ] **2.2.2** — **Modelo SQLAlchemy (`src/db/models.py`):** Añadir columna `db_names` como `Text` (almacenará JSON stringificado `'["bd1","bd2"]'`). Añadir property que parsee el JSON a lista.
- [ ] **2.2.3** — **CRUD (`src/db/crud.py`):** Actualizar `job_create` y `job_update` para serializar/deserializar `db_names`.
- [ ] **2.2.4** — **job_manager.py:** Modificar `run_job()` (línea ~396) para que, al inicio del pipeline:
  1. Determine la lista de BDs: `dbs = job.db_names_list or ([job.db_name] if job.db_name else [])`.
  2. Itere sobre cada BD con un `for db_name in dbs:` ejecutando el volcado (`dump`) secuencialmente.
  3. Comprima y suba cada volcado individualmente.
  4. Los logs deben indicar claramente: `"Procesando BD 1/3: mi_bd_1"`.
- [ ] **2.2.5** — **Frontend (HTML):** Reemplazar el input `#dbName` por un contenedor con:
  - Un campo de texto con botón "Añadir" para escribir nombres de BD manualmente.
  - Una lista de checkboxes que se puebla dinámicamente con las BDs descubiertas via `discovery`.
  - Cada BD añadida se muestra como un "chip" / tag con un botón "×" para eliminar.
- [ ] **2.2.6** — **Frontend (JS):** Modificar `initJobFormValidation()` para recoger el array de `db_names` de los chips/checkboxes y enviarlo en el payload de la API. El payload debe quedar como: `{ ..., db_names: ["bd1", "bd2"], db_name: null }`.
- [ ] **2.2.7** — **Retrocompatibilidad:** Si un Job existente tiene `db_name` pero no `db_names`, tratarlo como una lista con un solo elemento. Los Jobs existentes deben seguir funcionando sin migración manual.
- [ ] **2.2.8** — Añadir traducciones i18n: `label_select_databases`, `btn_add_database`, `ph_database_name`, `chip_remove`, `help_multiple_dbs`.

---

## 🔴 FASE 3: Lógica Core y Bugs Backend

> **Impacto:** Backend puro. Archivos: `src/core/job_manager.py`, `src/processors/compressor.py`

### 3.1 — Lógica de Compresión (.zip) Condicional

**Diagnóstico:**
Actualmente, `job_manager.py` **SIEMPRE comprime** el volcado a `.zip` (línea ~688-705), sin importar si el usuario quiere compresión o no. El modelo `JobBase` tiene un campo `compress: bool | None = True` (en `models.py`, línea ~36), pero **nunca se usa** en el pipeline de `run_job()`. No hay ningún `if job.compress:` antes de llamar a `self.compressor.compress(dump_path)`.

Además, cuando no se quiere comprimir, la lógica actual nombra el archivo como `{job.name}_{timestamp}.sql.zip` (línea ~723), lo cual es incorrecto si no hay compresión.

**Plan de Acción:**

- [ ] **3.1.1** — **Frontend (HTML):** Asegurar que existe un checkbox visible en el formulario para activar/desactivar la compresión. Añadirlo en la sección "Destino del Backup", después de retención:
  ```html
  <div class="flex items-center gap-3 mt-4">
      <input type="checkbox" id="jobCompress" checked
          class="w-4 h-4 text-brand-500 border-slate-300 rounded focus:ring-brand-500">
      <label for="jobCompress" class="text-sm text-slate-600 dark:text-slate-400">
          Comprimir backup en .zip
          <span class="text-xs text-slate-400 block">
              (recomendado: ocupa menos espacio)
          </span>
      </label>
  </div>
  ```
- [ ] **3.1.2** — **Frontend (JS):** Incluir `compress: document.getElementById('jobCompress')?.checked ?? true` en el objeto `jobData` dentro de `initJobFormValidation()` (línea ~624). Cargar el valor en `setFormEditMode()`.
- [ ] **3.1.3** — **Backend (job_manager.py):** En el paso "4. Comprimir el Archivo" (línea ~688), añadir la condición:
  ```python
  if job.compress and job.db_type != "sync":
      # Comprimir como hasta ahora
      compressed_path = self.compressor.compress(dump_path)
  elif job.db_type != "sync":
      # SIN compresión: crear carpeta con nombre de tarea y mover archivos .sql sueltos
      task_folder = Path(job.dest_local_path or str(Path.cwd() / "backups")) / job.name
      task_folder.mkdir(parents=True, exist_ok=True)
      final_name = f"{job.name}_{timestamp}{suffix}"
      final_sql_path = task_folder / final_name
      shutil.move(str(dump_path), str(final_sql_path))
      compressed_path = final_sql_path
      file_size = final_sql_path.stat().st_size
  ```
- [ ] **3.1.4** — Ajustar el naming del archivo final (línea ~722-726) para que NO añada `.zip` si no hay compresión:
  ```python
  if job.compress:
      final_name = f"{job.name}_{timestamp}.sql.zip"
  else:
      final_name = f"{job.name}_{timestamp}{suffix}"
  ```
- [ ] **3.1.5** — Actualizar los logs del pipeline para reflejar si se comprimió o no. Si no se comprime, el log debe decir: `"Compresión desactivada. Guardando archivo sin comprimir."`.
- [ ] **3.1.6** — Añadir traducciones i18n: `label_compress_zip`, `help_compress_zip`.

---

### 3.2 — Bug de RUNNING Infinito (Proceso bloqueado en compresión)

**Diagnóstico:**
El `run_job()` en `job_manager.py` es un método `async` (línea ~396). Pero `self.compressor.compress()` (línea ~697) es una operación **síncrona** (CPU-bound) que se ejecuta en el hilo principal del event loop de asyncio. Si el archivo es grande, esto bloquea todo el event loop, impidiendo que FastAPI procese otras requests (incluida la propia actualización de estado del frontend vía polling).

Además, el `shutil.make_archive()` para carpetas tipo `folder` (línea ~597) también es síncrono y puede bloquearse en carpetas grandes.

La combinación de:
1. Compresión síncrona bloqueante en el event loop async.
2. Posible timeout o deadlock si el archivo temporal está en un volumen lento/lleno.
3. Falta de timeout en la operación de compresión.

...provoca que el `RunHistory` se quede en estado `RUNNING` indefinidamente porque el `except` general (línea ~943) nunca se alcanza.

**Plan de Acción:**

- [ ] **3.2.1** — **Mover compresión a un thread:** Envolver `self.compressor.compress()` en `asyncio.to_thread()` para que no bloquee el event loop:
  ```python
  import asyncio
  compressed_path = await asyncio.to_thread(self.compressor.compress, dump_path)
  ```
- [ ] **3.2.2** — **Mover `shutil.make_archive` a thread:** Igualmente para la compresión de carpetas (línea ~597):
  ```python
  archive_path_str = await asyncio.to_thread(
      shutil.make_archive, base_name, "zip", staging_dir
  )
  ```
- [ ] **3.2.3** — **Timeout global del pipeline:** Añadir un timeout de seguridad al `run_job()` completo. Envolver la ejecución del pipeline en `asyncio.wait_for()` con un timeout configurable (ej: 2 horas por defecto):
  ```python
  try:
      await asyncio.wait_for(self._execute_pipeline(job, run, db), timeout=7200)
  except asyncio.TimeoutError:
      history_manager.finish_run(db, run.id, status="failed",
          error_message="Timeout: El pipeline excedió el tiempo máximo (2h).")
  ```
- [ ] **3.2.4** — **Limpieza de RUNNINGs huérfanos:** Añadir un chequeo al inicio de `run_job()` que busque runs en estado `RUNNING` con `started_at` anterior a 3 horas y los marque automáticamente como `FAILED` con mensaje `"Marcado como fallido: excedió tiempo máximo sin completar."`. Esto limpia estados corruptos de ejecuciones anteriores.
- [ ] **3.2.5** — **Log de progreso durante la compresión:** Antes de iniciar la compresión, registrar un log `"Comprimiendo archivo (esto puede tardar varios minutos para archivos grandes)..."` y después del `to_thread`, registrar `"Compresión finalizada."`. Esto da visibilidad al usuario de que algo está pasando.
- [ ] **3.2.6** — **Verificar espacio en disco antes de comprimir:** Antes de llamar a `compress()`, verificar que hay espacio suficiente en el directorio temporal (`shutil.disk_usage()`). Si el espacio libre es menor al tamaño del dump × 1.5, registrar un error claro: `"No hay suficiente espacio en disco para comprimir el backup."` y fallar con `FAILED` en vez de colgarse.

---

## 📌 Orden de Ejecución Recomendado

```
Fase 1 (Frontend puro — sin riesgo de romper el backend)
  └─ 1.2 Bug de Clones      ← Fix rápido, impacto inmediato
  └─ 1.1 Botones Perdidos    ← Fix rápido, impacto inmediato
  └─ 1.3 Sidebar Unificada   ← Cambio simple en app.js
  └─ 1.4 Lavado de Cara      ← Cambio cosmético, requiere review visual

Fase 3 (Backend bugs — crítico antes de añadir features)
  └─ 3.2 Bug RUNNING infinito ← MÁS URGENTE de todo el plan
  └─ 3.1 Lógica de compresión ← Depende de 3.2 estar resuelto

Fase 2 (Features nuevas — una vez los bugs estén arreglados)
  └─ 2.1 Crear Carpeta        ← Más sencillo
  └─ 2.2 Múltiples BDs        ← Más complejo, requiere migración de modelo
```

---

## 🧪 Criterios de Aceptación por Fase

### Fase 1
- [ ] Los botones "Guardar" y "Cancelar" son visibles **siempre**, sin scroll, en cualquier resolución.
- [ ] Hacer clic en "Editar" → "Editar" → "Editar" sobre el mismo Job produce exactamente 1 botón "Cancelar".
- [ ] Todos los botones de acción en la sidebar muestran el icono ▶️ (play), nunca 🔄 (sync).
- [ ] Los inputs están alineados, con espaciado uniforme y placeholders comprensibles para no-técnicos.

### Fase 2
- [ ] El usuario puede crear una carpeta nueva desde dentro del explorador de archivos sin salir de la app.
- [ ] El usuario puede seleccionar 3 BDs a la vez y el pipeline las procesa secuencialmente.
- [ ] Un Job existente con una sola BD sigue funcionando sin modificación.

### Fase 3
- [ ] Un backup sin compresión genera una carpeta con el nombre de la tarea y los `.sql` sueltos dentro.
- [ ] Un backup con compresión genera un `.zip` como antes.
- [ ] Ejecutar un backup de un archivo de 500MB+ no deja el estado en RUNNING eternamente.
- [ ] Si la compresión falla por espacio, el estado es FAILED con un mensaje claro, no RUNNING.

---

> **Nota:** Este documento es el plan. No se debe modificar código hasta que el plan sea aprobado fase por fase.
