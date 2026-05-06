/**
 * api.js — Capa de comunicación con la API REST de FastAPI.
 *
 * Centraliza todas las llamadas fetch hacia /api/v1/ para que los
 * componentes no tengan que conocer las URLs ni gestionar errores HTTP.
 *
 * Patrón: objeto global `API` con métodos async por recurso.
 * Uso: await API.jobs.list()  |  await API.jobs.create(data)
 */

const API_BASE = '/api/v1';

/**
 * Wrapper base de fetch con manejo de errores y parsing JSON automático.
 * @param {string} url - Ruta relativa a API_BASE.
 * @param {RequestInit} options - Opciones de fetch.
 * @returns {Promise<any>} - Respuesta JSON parseada.
 * @throws {Error} - Con mensaje del servidor si el status >= 400.
 */
async function apiFetch(url, options = {}) {
  const defaults = {
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
  };
  const response = await fetch(API_BASE + url, { ...defaults, ...options });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

/** API de Jobs */
const API = {
  jobs: {
    /** @returns {Promise<Array>} Lista de todos los jobs */
    list:   (params = {}) => apiFetch('/jobs?' + new URLSearchParams(params)),
    /** @param {Object} data - JobCreate payload */
    create: (data) => apiFetch('/jobs', { method: 'POST', body: JSON.stringify(data) }),
    /** @param {number} id */
    get:    (id)   => apiFetch(`/jobs/${id}`),
    /** @param {number} id @param {Object} data - JobUpdate payload */
    update: (id, data) => apiFetch(`/jobs/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    /** @param {number} id */
    delete: (id)   => apiFetch(`/jobs/${id}`, { method: 'DELETE' }),
    /** @param {number} id - Dispara ejecución manual, devuelve { run_id } */
    run:    (id)   => apiFetch(`/jobs/${id}/run`, { method: 'POST' }),
    enable: (id)   => apiFetch(`/jobs/${id}/enable`, { method: 'POST' }),
    disable:(id)   => apiFetch(`/jobs/${id}/disable`, { method: 'POST' }),
  },

  history: {
    list:       (params = {}) => apiFetch('/history?' + new URLSearchParams(params)),
    listByJob:  (jobId, params = {}) => apiFetch(`/history/job/${jobId}?` + new URLSearchParams(params)),
    get:        (runId) => apiFetch(`/history/run/${runId}`),
    deleteRun:  (runId) => apiFetch(`/history/run/${runId}`, { method: 'DELETE' }),
  },

  logs: {
    get:    (runId, params = {}) => apiFetch(`/logs/${runId}?` + new URLSearchParams(params)),
    /** Devuelve un EventSource para SSE (no usa apiFetch) */
    stream: (runId) => new EventSource(`${API_BASE}/logs/${runId}/stream`),
  },

  settings: {
    get:       () => apiFetch('/settings'),
    update:    (data) => apiFetch('/settings', { method: 'PUT', body: JSON.stringify(data) }),
    testEmail: () => apiFetch('/settings/test-email', { method: 'POST' }),
  },
};

window.API = API;
