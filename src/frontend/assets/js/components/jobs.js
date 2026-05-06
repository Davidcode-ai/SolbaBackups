/**
 * components/jobs.js — Componente de gestión de Jobs de Backup.
 *
 * Responsabilidades:
 *  - Renderizar la lista de jobs con acciones (run, enable/disable, edit, delete).
 *  - Abrir el modal de creación/edición de un job (wizard de 3 pasos).
 *  - Llamar a la API y actualizar la UI de forma reactiva.
 */

const jobsComponent = {
  jobs: [],

  /** Renderiza el componente en el contenedor dado. */
  async render(container) {
    container.innerHTML = `
      <div class="animate-fade-in">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-lg font-semibold text-white">Jobs de Backup</h2>
          <button onclick="jobsComponent.openCreateModal()" class="btn btn-primary">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
            Nuevo Job
          </button>
        </div>
        <div id="jobs-list" class="space-y-3">
          <div class="text-muted text-sm text-center py-8">Cargando jobs...</div>
        </div>
      </div>`;
    await this.loadJobs();
  },

  /** Carga los jobs desde la API y actualiza el listado. */
  async loadJobs() {
    try {
      this.jobs = await API.jobs.list();
      this._renderList();
    } catch (e) {
      Toast.error('Error al cargar jobs: ' + e.message);
    }
  },

  /** Renderiza la tabla de jobs. */
  _renderList() {
    const container = document.getElementById('jobs-list');
    if (!this.jobs.length) {
      container.innerHTML = `<div class="stat-card text-center py-12 text-muted">
        <p class="text-sm">No hay jobs configurados todavía.</p>
        <button onclick="jobsComponent.openCreateModal()" class="btn btn-primary mt-4">Crear primer Job</button>
      </div>`;
      return;
    }
    container.innerHTML = `
      <div class="stat-card p-0 overflow-hidden">
        <table class="data-table">
          <thead><tr>
            <th>Nombre</th><th>Base de Datos</th><th>Destino</th>
            <th>Próximo Run</th><th>Estado</th><th>Acciones</th>
          </tr></thead>
          <tbody>
            ${this.jobs.map(job => this._renderRow(job)).join('')}
          </tbody>
        </table>
      </div>`;
  },

  /** Renderiza una fila de la tabla para un job. */
  _renderRow(job) {
    const badge = job.is_active
      ? '<span class="badge badge-success">Activo</span>'
      : '<span class="badge badge-muted">Pausado</span>';
    const nextRun = job.schedule_next_run
      ? new Date(job.schedule_next_run).toLocaleString('es-ES')
      : '<span class="text-muted">—</span>';
    return `<tr>
      <td class="font-medium text-white">${job.name}</td>
      <td><span class="font-mono text-xs bg-surface px-2 py-0.5 rounded">${job.db_type}</span> ${job.db_name}</td>
      <td>${job.dest_type}</td>
      <td class="text-sm text-muted">${nextRun}</td>
      <td>${badge}</td>
      <td>
        <div class="flex gap-2">
          <button onclick="jobsComponent.runJob(${job.id})" title="Ejecutar ahora" class="btn btn-ghost py-1 px-2 text-xs">▶ Run</button>
          <button onclick="jobsComponent.openEditModal(${job.id})" class="btn btn-ghost py-1 px-2 text-xs">✏ Editar</button>
          <button onclick="jobsComponent.deleteJob(${job.id}, '${job.name}')" class="btn btn-danger py-1 px-2 text-xs">✕</button>
        </div>
      </td>
    </tr>`;
  },

  /** Abre el modal de creación de un nuevo job. */
  openCreateModal() {
    showModal(`
      <div class="p-6">
        <h3 class="text-lg font-semibold text-white mb-4">Nuevo Job de Backup</h3>
        <form id="job-form" onsubmit="jobsComponent.submitCreate(event)">
          <div class="space-y-4">
            <div>
              <label class="block text-sm text-muted mb-1">Nombre del Job *</label>
              <input id="job-name" type="text" class="form-input" placeholder="ej: backup-produccion-diario" required>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm text-muted mb-1">Motor de BD *</label>
                <select id="job-db-type" class="form-input" required>
                  <option value="">Seleccionar...</option>
                  <option value="postgresql">PostgreSQL</option>
                  <option value="mysql">MySQL / MariaDB</option>
                  <option value="sqlserver">SQL Server</option>
                  <option value="sqlite">SQLite</option>
                </select>
              </div>
              <div>
                <label class="block text-sm text-muted mb-1">Nombre de la BD *</label>
                <input id="job-db-name" type="text" class="form-input" placeholder="mi_base_de_datos" required>
              </div>
            </div>
            <div class="grid grid-cols-3 gap-4">
              <div class="col-span-2">
                <label class="block text-sm text-muted mb-1">Host</label>
                <input id="job-db-host" type="text" class="form-input" value="localhost">
              </div>
              <div>
                <label class="block text-sm text-muted mb-1">Puerto</label>
                <input id="job-db-port" type="number" class="form-input" placeholder="5432">
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm text-muted mb-1">Usuario</label>
                <input id="job-db-user" type="text" class="form-input">
              </div>
              <div>
                <label class="block text-sm text-muted mb-1">Contraseña</label>
                <input id="job-db-pass" type="password" class="form-input">
              </div>
            </div>
            <div>
              <label class="block text-sm text-muted mb-1">Destino *</label>
              <select id="job-dest-type" class="form-input" required>
                <option value="local">Carpeta Local / Red</option>
                <option value="google_drive">Google Drive</option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-muted mb-1">Ruta de destino</label>
              <input id="job-dest-path" type="text" class="form-input" placeholder="C:\\Backups\\">
            </div>
          </div>
          <div class="flex justify-end gap-3 mt-6">
            <button type="button" onclick="closeModal()" class="btn btn-ghost">Cancelar</button>
            <button type="submit" class="btn btn-primary">Crear Job</button>
          </div>
        </form>
      </div>`);
  },

  /** Abre el modal de edición con los datos del job. */
  async openEditModal(jobId) {
    try {
      const job = await API.jobs.get(jobId);
      Toast.info(`Editando: ${job.name}`);
      // TODO: rellenar formulario con datos del job
      this.openCreateModal();
    } catch (e) { Toast.error(e.message); }
  },

  /** Envía el formulario de creación. */
  async submitCreate(e) {
    e.preventDefault();
    const payload = {
      name:      document.getElementById('job-name').value,
      db_type:   document.getElementById('job-db-type').value,
      db_name:   document.getElementById('job-db-name').value,
      db_host:   document.getElementById('job-db-host').value || null,
      db_port:   parseInt(document.getElementById('job-db-port').value) || null,
      db_user:   document.getElementById('job-db-user').value || null,
      db_password: document.getElementById('job-db-pass').value || null,
      dest_type: document.getElementById('job-dest-type').value,
      dest_local_path: document.getElementById('job-dest-path').value || null,
    };
    try {
      await API.jobs.create(payload);
      closeModal();
      Toast.success(`Job "${payload.name}" creado correctamente`);
      await this.loadJobs();
    } catch (e) { Toast.error('Error al crear job: ' + e.message); }
  },

  /** Dispara una ejecución manual del job. */
  async runJob(jobId) {
    try {
      const result = await API.jobs.run(jobId);
      Toast.success(`Ejecución iniciada (run_id: ${result.run_id})`);
    } catch (e) { Toast.error('Error al ejecutar job: ' + e.message); }
  },

  /** Elimina un job tras confirmación. */
  async deleteJob(jobId, name) {
    if (!confirm(`¿Eliminar el job "${name}"? Esta acción no se puede deshacer.`)) return;
    try {
      await API.jobs.delete(jobId);
      Toast.success(`Job "${name}" eliminado`);
      await this.loadJobs();
    } catch (e) { Toast.error('Error al eliminar: ' + e.message); }
  },
};

window.jobsComponent = jobsComponent;
