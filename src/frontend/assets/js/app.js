/**
 * app.js — Router SPA y utilidades globales de SolbaBackups.
 *
 * Gestiona:
 *  - Navegación entre páginas (sin recarga de página).
 *  - Registro y ciclo de vida de componentes.
 *  - Sistema de Toast notifications.
 *  - Función showModal / closeModal global.
 */

const PAGES = {
  dashboard: { title: 'Dashboard',       component: () => window.dashboardComponent },
  jobs:      { title: 'Jobs de Backup',  component: () => window.jobsComponent },
  history:   { title: 'Historial',       component: () => window.historyComponent },
  logs:      { title: 'Logs',            component: () => window.logsComponent },
  settings:  { title: 'Configuración',   component: () => window.settingsComponent },
};

const app = {
  currentPage: null,

  /** Navega a una página por su key. */
  navigate(page) {
    if (!PAGES[page]) return;
    // Actualizar nav links activos
    document.querySelectorAll('.nav-link').forEach(el => {
      el.classList.toggle('active', el.dataset.page === page);
    });
    // Actualizar título del topbar
    document.getElementById('page-title').textContent = PAGES[page].title;
    // Renderizar el componente
    const component = PAGES[page].component();
    if (component && typeof component.render === 'function') {
      document.getElementById('main-content').innerHTML = '';
      component.render(document.getElementById('main-content'));
    }
    this.currentPage = page;
    window.location.hash = page;
  },

  /** Lee el hash de la URL para restaurar la navegación al recargar. */
  init() {
    const hash = window.location.hash.replace('#', '') || 'dashboard';
    this.navigate(PAGES[hash] ? hash : 'dashboard');
  },
};

/** Sistema de Toast notifications global. */
const Toast = {
  show(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity .3s';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },
  success: (msg) => Toast.show(msg, 'success'),
  error:   (msg) => Toast.show(msg, 'error'),
  info:    (msg) => Toast.show(msg, 'info'),
};

/** Abre el modal global con HTML arbitrario. */
function showModal(html) {
  document.getElementById('modal-content').innerHTML = html;
  document.getElementById('global-modal').classList.remove('hidden');
}

/** Cierra el modal global. */
function closeModal() {
  document.getElementById('global-modal').classList.add('hidden');
  document.getElementById('modal-content').innerHTML = '';
}

// Cerrar modal al hacer clic fuera del contenido
document.getElementById('global-modal').addEventListener('click', (e) => {
  if (e.target.id === 'global-modal') closeModal();
});

// Exponer globalmente
window.app   = app;
window.Toast = Toast;
window.showModal  = showModal;
window.closeModal = closeModal;

// Arrancar la app cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => app.init());
