/**
 * components/settings.js — Componente de Configuración Global.
 */
const settingsComponent = {
  async render(container) {
    container.innerHTML = `<div class="animate-fade-in max-w-2xl">
      <h2 class="text-lg font-semibold text-white mb-6">Configuración</h2>
      <div class="text-muted text-sm">Cargando configuración...</div>
    </div>`;
    try {
      const cfg = await API.settings.get();
      container.innerHTML = `
        <div class="animate-fade-in max-w-2xl space-y-6">
          <h2 class="text-lg font-semibold text-white">Configuración Global</h2>
          <form onsubmit="settingsComponent.save(event)">
            <div class="stat-card space-y-4">
              <h3 class="text-sm font-semibold text-white">Notificaciones SMTP</h3>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs text-muted mb-1">Servidor SMTP</label>
                  <input id="cfg-smtp-host" type="text" class="form-input" value="${cfg.smtp_host||''}">
                </div>
                <div>
                  <label class="block text-xs text-muted mb-1">Puerto</label>
                  <input id="cfg-smtp-port" type="number" class="form-input" value="${cfg.smtp_port||587}">
                </div>
              </div>
              <div>
                <label class="block text-xs text-muted mb-1">Email destino notificaciones</label>
                <input id="cfg-notify-email" type="email" class="form-input" value="${cfg.notify_recipient||''}">
              </div>
            </div>
            <div class="stat-card space-y-4 mt-4">
              <h3 class="text-sm font-semibold text-white">Herramientas Externas</h3>
              <div>
                <label class="block text-xs text-muted mb-1">Ruta de pg_dump</label>
                <input id="cfg-pgdump" type="text" class="form-input" value="${cfg.pg_dump_path||''}" placeholder="pg_dump (en PATH)">
              </div>
              <div>
                <label class="block text-xs text-muted mb-1">Ruta de mysqldump</label>
                <input id="cfg-mysqldump" type="text" class="form-input" value="${cfg.mysqldump_path||''}" placeholder="mysqldump (en PATH)">
              </div>
            </div>
            <div class="flex gap-3 mt-6">
              <button type="submit" class="btn btn-primary">Guardar Cambios</button>
              <button type="button" onclick="settingsComponent.testEmail()" class="btn btn-ghost">Enviar email de prueba</button>
            </div>
          </form>
        </div>`;
    } catch (e) { Toast.error('Error al cargar configuración: ' + e.message); }
  },

  async save(e) {
    e.preventDefault();
    const payload = {
      smtp_host: document.getElementById('cfg-smtp-host').value || null,
      smtp_port: parseInt(document.getElementById('cfg-smtp-port').value) || null,
      notify_recipient: document.getElementById('cfg-notify-email').value || null,
      pg_dump_path: document.getElementById('cfg-pgdump').value || null,
      mysqldump_path: document.getElementById('cfg-mysqldump').value || null,
    };
    try {
      await API.settings.update(payload);
      Toast.success('Configuración guardada');
    } catch (e) { Toast.error('Error: ' + e.message); }
  },

  async testEmail() {
    try {
      await API.settings.testEmail();
      Toast.success('Email de prueba enviado');
    } catch (e) { Toast.error('Error al enviar email: ' + e.message); }
  },
};
window.settingsComponent = settingsComponent;
