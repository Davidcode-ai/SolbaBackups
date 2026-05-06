/**
 * components/dashboard.js — Componente Dashboard de SolbaBackups.
 * Muestra estadísticas resumen y últimas 5 ejecuciones.
 */
const dashboardComponent = {
  async render(container) {
    container.innerHTML = `
      <div class="animate-fade-in space-y-6">
        <h2 class="text-lg font-semibold text-white">Dashboard</h2>
        <div id="stats-grid" class="grid grid-cols-4 gap-4">
          ${['Jobs activos','Runs hoy','Éxitos','Fallos'].map(t => `
            <div class="stat-card">
              <p class="text-xs text-muted uppercase tracking-wide mb-1">${t}</p>
              <p class="text-2xl font-bold text-white">—</p>
            </div>`).join('')}
        </div>
        <div>
          <h3 class="text-sm font-semibold text-white mb-3">Últimas Ejecuciones</h3>
          <div id="recent-runs" class="stat-card p-0 overflow-hidden">
            <div class="text-center text-muted text-sm py-6">Cargando...</div>
          </div>
        </div>
      </div>`;
    await this._loadData();
  },

  async _loadData() {
    try {
      const [jobs, runs] = await Promise.all([
        API.jobs.list({ is_active: true }),
        API.history.list({ page: 1, page_size: 5 }),
      ]);
      // Stats
      const today = new Date().toDateString();
      const runsToday  = runs.filter(r => new Date(r.started_at).toDateString() === today);
      const successes  = runsToday.filter(r => r.status === 'success').length;
      const failures   = runsToday.filter(r => r.status === 'failed').length;
      const vals = [jobs.length, runsToday.length, successes, failures];
      document.querySelectorAll('#stats-grid .stat-card').forEach((card, i) => {
        card.querySelector('.text-2xl').textContent = vals[i];
      });
      // Recent runs
      const container = document.getElementById('recent-runs');
      if (!runs.length) { container.innerHTML = '<div class="text-center text-muted py-6 text-sm">Sin ejecuciones todavía</div>'; return; }
      const statusMap = { success:'badge-success', failed:'badge-danger', running:'badge-running', warning:'badge-warning' };
      container.innerHTML = `<table class="data-table">
        <thead><tr><th>Job</th><th>Inicio</th><th>Estado</th><th>Duración</th></tr></thead>
        <tbody>${runs.map(r => `<tr>
          <td class="font-medium text-white">${r.job_name}</td>
          <td class="text-sm text-muted">${new Date(r.started_at).toLocaleString('es-ES')}</td>
          <td><span class="badge ${statusMap[r.status]||'badge-muted'}">${r.status}</span></td>
          <td class="text-sm">${r.duration_secs ? r.duration_secs.toFixed(1)+'s' : '—'}</td>
        </tr>`).join('')}</tbody>
      </table>`;
    } catch (e) { Toast.error('Error al cargar dashboard: ' + e.message); }
  },
};
window.dashboardComponent = dashboardComponent;
