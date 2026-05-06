/**
 * components/history.js — Componente de Historial de Ejecuciones.
 * Lista paginada de runs con filtros y enlace a logs.
 */
const historyComponent = {
  runs: [], page: 1, pageSize: 25,

  async render(container) {
    container.innerHTML = `
      <div class="animate-fade-in">
        <h2 class="text-lg font-semibold text-white mb-6">Historial de Ejecuciones</h2>
        <div class="stat-card p-0 overflow-hidden">
          <table class="data-table">
            <thead><tr>
              <th>Job</th><th>Inicio</th><th>Duración</th><th>Estado</th><th>Tamaño</th><th>Logs</th>
            </tr></thead>
            <tbody id="history-body"><tr><td colspan="6" class="text-center text-muted py-6">Cargando...</td></tr></tbody>
          </table>
        </div>
      </div>`;
    await this.loadHistory();
  },

  async loadHistory() {
    try {
      this.runs = await API.history.list({ page: this.page, page_size: this.pageSize });
      const body = document.getElementById('history-body');
      if (!body) return;
      if (!this.runs.length) {
        body.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-6">Sin ejecuciones todavía</td></tr>';
        return;
      }
      body.innerHTML = this.runs.map(r => {
        const statusMap = { success:'badge-success', failed:'badge-danger', running:'badge-running', warning:'badge-warning' };
        const badge = `<span class="badge ${statusMap[r.status] || 'badge-muted'}">${r.status}</span>`;
        const dur   = r.duration_secs ? `${r.duration_secs.toFixed(1)}s` : '—';
        const size  = r.file_size_bytes ? (r.file_size_bytes / 1024 / 1024).toFixed(2) + ' MB' : '—';
        const start = new Date(r.started_at).toLocaleString('es-ES');
        return `<tr>
          <td class="font-medium text-white">${r.job_name}</td>
          <td class="text-sm text-muted">${start}</td>
          <td class="text-sm">${dur}</td>
          <td>${badge}</td>
          <td class="text-sm text-muted">${size}</td>
          <td><button onclick="logsComponent.viewRun(${r.id}); app.navigate('logs');" class="btn btn-ghost py-1 px-2 text-xs">Ver logs</button></td>
        </tr>`;
      }).join('');
    } catch (e) { Toast.error('Error al cargar historial: ' + e.message); }
  },
};
window.historyComponent = historyComponent;
