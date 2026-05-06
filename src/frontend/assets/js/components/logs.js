/**
 * components/logs.js — Componente Visor de Logs.
 * Muestra logs de una ejecución y hace streaming SSE si está en curso.
 */
const logsComponent = {
  currentRunId: null,
  eventSource: null,

  async render(container) {
    container.innerHTML = `
      <div class="animate-fade-in">
        <h2 class="text-lg font-semibold text-white mb-4">Visor de Logs</h2>
        <div id="log-run-selector" class="mb-4 text-muted text-sm">
          Selecciona una ejecución desde el <button onclick="app.navigate('history')" class="text-primary-light underline">Historial</button>.
        </div>
        <div id="log-viewer" class="hidden"></div>
      </div>`;
    if (this.currentRunId) await this.viewRun(this.currentRunId);
  },

  /** Carga logs de un run (batch o SSE si está en curso). */
  async viewRun(runId) {
    this.currentRunId = runId;
    const viewer = document.getElementById('log-viewer');
    if (!viewer) return;
    viewer.classList.remove('hidden');
    viewer.innerHTML = '<div class="text-muted text-sm">Cargando logs...</div>';

    try {
      const run = await API.history.get(runId);
      if (run.status === 'running') {
        this._startSSE(runId, viewer);
      } else {
        const logs = await API.logs.get(runId);
        this._renderLogs(logs, viewer);
      }
    } catch (e) { viewer.innerHTML = `<div class="text-danger">${e.message}</div>`; }
  },

  /** Renderiza un array de log entries en el viewer. */
  _renderLogs(logs, viewer) {
    if (!logs.length) { viewer.innerHTML = '<div class="text-muted text-sm">Sin logs para este run.</div>'; return; }
    viewer.innerHTML = logs.map(l => `
      <div class="log-line">
        <span class="log-time">${new Date(l.timestamp).toLocaleTimeString('es-ES')}</span>
        <span class="log-level log-level-${l.level}">${l.level}</span>
        <span class="log-stage">${l.stage}</span>
        <span class="log-msg">${l.message}</span>
      </div>`).join('');
    viewer.scrollTop = viewer.scrollHeight;
  },

  /** Inicia SSE para ejecuciones en curso. */
  _startSSE(runId, viewer) {
    viewer.innerHTML = '';
    if (this.eventSource) this.eventSource.close();
    this.eventSource = API.logs.stream(runId);
    this.eventSource.addEventListener('log', (e) => {
      const l = JSON.parse(e.data);
      viewer.insertAdjacentHTML('beforeend', `
        <div class="log-line">
          <span class="log-time">${new Date(l.timestamp).toLocaleTimeString('es-ES')}</span>
          <span class="log-level log-level-${l.level}">${l.level}</span>
          <span class="log-stage">${l.stage}</span>
          <span class="log-msg">${l.message}</span>
        </div>`);
      viewer.scrollTop = viewer.scrollHeight;
    });
    this.eventSource.addEventListener('done', () => this.eventSource.close());
    this.eventSource.onerror = () => this.eventSource.close();
  },
};
window.logsComponent = logsComponent;
