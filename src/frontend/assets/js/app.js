/**
 * app.js - Lógica principal de la UI para SolbaBackups
 */

let isFormDirty = false; // Estado para saber si hay cambios sin guardar
let currentEditingJobId = null; // ID del job en modo edición (contraseña en servidor)

const SPAIN_TIMEZONE = 'Europe/Madrid';

/** Interpreta fechas del servidor (UTC sin zona) y las muestra en hora de España. */
function parseUtcDate(isoValue) {
    if (!isoValue) return null;
    let s = String(isoValue).trim();
    if (!s) return null;
    if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) {
        s = s.includes('T') ? `${s}Z` : `${s.replace(' ', 'T')}Z`;
    }
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? null : d;
}

function formatDateTimeSpain(isoValue) {
    const d = parseUtcDate(isoValue);
    if (!d) return 'N/A';
    return d.toLocaleString('es-ES', {
        timeZone: SPAIN_TIMEZONE,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
}

function getScheduleTimeValue() {
    const hourSel = document.getElementById('jobScheduleHour');
    const minSel = document.getElementById('jobScheduleMinute');
    if (!hourSel || !minSel) return '';
    const hour = hourSel.value;
    const minute = minSel.value;
    if (hour === '' || minute === '') return '';
    return `${hour}:${minute}`;
}

function setScheduleTimeValue(timeStr) {
    const hourSel = document.getElementById('jobScheduleHour');
    const minSel = document.getElementById('jobScheduleMinute');
    if (!hourSel || !minSel) return;
    const parts = (timeStr || '02:00').split(':');
    const h = Math.min(23, Math.max(0, parseInt(parts[0], 10) || 0));
    const m = Math.min(59, Math.max(0, parseInt(parts[1], 10) || 0));
    hourSel.value = String(h).padStart(2, '0');
    minSel.value = String(m).padStart(2, '0');
}

function initScheduleTimeSelects() {
    const hourSel = document.getElementById('jobScheduleHour');
    const minSel = document.getElementById('jobScheduleMinute');
    const domSel = document.getElementById('jobScheduleDayOfMonth');
    if (hourSel && hourSel.options.length === 0) {
        for (let h = 0; h < 24; h++) {
            const v = String(h).padStart(2, '0');
            hourSel.add(new Option(v, v));
        }
    }
    if (minSel && minSel.options.length === 0) {
        for (let m = 0; m < 60; m++) {
            const v = String(m).padStart(2, '0');
            minSel.add(new Option(v, v));
        }
    }
    if (domSel && domSel.options.length === 0) {
        for (let d = 1; d <= 28; d++) {
            domSel.add(new Option(String(d), String(d)));
        }
    }
    setScheduleTimeValue('02:00');
    if (domSel && !domSel.value) domSel.value = '1';
}

document.addEventListener('DOMContentLoaded', async () => {
    // Inicializar Tema Claro/Oscuro
    initTheme();

    // 0. Cargar configuración inicial (como el idioma) de forma bloqueante
    await loadInitialSettings();

    // 1. Autodescubrimiento
    await loadDiscovery();

    // 2. Obtener Jobs y pintar pantalla central
    await loadJobs();

    // 3. Obtener Historial y pintar panel derecho
    await loadHistory();

    // 3.5 Obtener Estadísticas (Centro de Mando)
    await loadStats();

    // Aplicar traducción de nuevo por si se generó contenido dinámico en español
    const langSelect = document.getElementById('s-language');
    if (langSelect && langSelect.value !== 'es') {
        applyTranslations(langSelect.value);
    }

    // 4. Inicializar validación del formulario
    initScheduleTimeSelects();
    initJobFormValidation();

    // 5. Iniciar polling (Radar) silencioso
    setupPolling();

    // 6. Inicializar el Visor de Logs (modal terminal)
    initLogViewer();

    // 7. Inicializar el modal de Ajustes Globales
    initSettingsModal();

    // 8. Chequear estado de Google Drive
    checkGoogleDriveStatus();
});

async function loadInitialSettings() {
    try {
        let result = await api.getSettings();
        let settings = result.settings || result;
        if (settings) {
            if (typeof populateSettingsForm === 'function') {
                populateSettingsForm(settings);
            }
        }
    } catch (e) {
        console.error("Error cargando configuración inicial:", e);
    }
}

/**
 * Inicializa el tema leyendo localStorage y asigna el evento al botón
 */
function initTheme() {
    const themeBtn = document.getElementById('themeToggleBtn');
    if (!themeBtn) return;

    // Leer de localStorage o sistema por defecto
    const isDark = localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches);

    if (isDark) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }

    themeBtn.addEventListener('click', () => {
        document.documentElement.classList.toggle('dark');
        const isNowDark = document.documentElement.classList.contains('dark');
        localStorage.theme = isNowDark ? 'dark' : 'light';
    });
}

/**
 * Carga la lista de Jobs desde la API y los renderiza en la pantalla central.
 * Incluye botones de Ejecutar, Editar y Borrar en cada tarjeta.
 */
async function loadJobs(isSilent = false) {
    const container = document.getElementById('sidebar-jobs-container');
    if (!container) return;

    try {
        const jobs = await api.getJobs();
        container.innerHTML = '';

        if (jobs.length === 0) {
            container.innerHTML = `
                <div class="flex flex-col items-center justify-center py-10 px-4 text-center">
                    <div class="w-14 h-14 bg-slate-100 dark:bg-surface-800 rounded-full flex items-center justify-center mb-3">
                        <svg class="w-6 h-6 text-slate-400 dark:text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                        </svg>
                    </div>
                    <p class="text-sm font-medium text-slate-800 dark:text-slate-200 mb-1">${t('empty_jobs_title')}</p>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mb-4">${t('empty_jobs_desc')}</p>
                    <button onclick="document.getElementById('jobName').focus();" class="bg-brand-500 hover:bg-brand-600 text-white px-4 py-2 rounded-lg text-xs font-medium transition-all shadow-sm">
                        ${t('empty_jobs_cta')}
                    </button>
                </div>
            `;
            return;
        }

        jobs.forEach(job => {
            const jobId = job._id || job.id || job.job_id;

            const jobBtn = document.createElement('div');
            jobBtn.className = 'w-full flex items-center justify-between px-3 py-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-surface-800 hover:text-slate-800 dark:hover:text-slate-200 rounded-lg group transition-colors text-left border border-transparent';
            jobBtn.dataset.jobId = jobId;

            let iconClass = "fa-solid fa-server";
            if (job.db_type === 'folder' || job.db_type === 'sync') iconClass = "fa-solid fa-folder-tree";
            else if (job.db_type === 'sqlite' || job.db_type === 'mdb') iconClass = "fa-solid fa-file-lines";

            let actionTitle = t('Ejecutar') || 'Ejecutar';

            jobBtn.innerHTML = `
                <div class="flex items-center gap-3 flex-1 min-w-0 cursor-pointer btn-edit-job" 
                    data-id="${jobId}"
                    data-name="${job.name || ''}"
                    data-description="${job.description || ''}"
                    data-schedule="${job.schedule_type || 'manual'}"
                    data-schedule-interval="${job.schedule_interval_minutes || ''}"
                    data-schedule-cron="${job.schedule_cron || ''}"
                    data-db-type="${job.db_type || ''}"
                    data-db-host="${job.db_host || ''}"
                    data-db-port="${job.db_port || ''}"
                    data-db-name="${job.db_name || ''}"
                    data-db-user="${job.db_user || ''}"
                    data-dest-type="${job.dest_type || 'local'}"
                    data-dest-local-path="${job.dest_local_path || ''}"
                    data-dest-gdrive-folder-id="${job.dest_gdrive_folder_id || ''}"
                    data-dest-gdrive-folder-name="${job.dest_gdrive_folder_name || ''}"
                    data-dest-retention-days="${job.dest_retention_days !== undefined ? job.dest_retention_days : 0}"
                    data-compress="${job.compress === true}"
                    data-last-run-status="${job.last_run_status || ''}">
                    <i class="${iconClass} w-4 text-center group-hover:text-brand-400 transition-colors"></i>
                    <div class="flex-1 truncate">
                        <p class="text-sm font-medium group-hover:text-brand-400 transition-colors">${job.name || 'Job sin nombre'}</p>
                        <p class="text-[10px] text-slate-500 truncate">${job.db_type} • ${job.schedule_type || 'manual'}</p>
                    </div>
                </div>
                
                <div class="flex items-center gap-1 shrink-0">
                    <button class="btn-ejecutar w-6 h-6 flex items-center justify-center rounded bg-brand-500/10 text-brand-400 hover:bg-brand-500 hover:text-white transition-colors" data-id="${jobId}" title="${actionTitle}">
                        <i class="fa-solid fa-play text-[10px]"></i>
                    </button>
                    <button class="btn-delete-job w-6 h-6 flex items-center justify-center rounded bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white transition-colors" data-id="${jobId}" title="${t('btn_delete')}">
                        <i class="fa-solid fa-trash-can text-[10px]"></i>
                    </button>
                </div>
            `;

            jobBtn.querySelector('.btn-ejecutar').addEventListener('click', handleRunJob);
            jobBtn.querySelector('.btn-edit-job').addEventListener('click', handleEditJob);
            jobBtn.querySelector('.btn-delete-job').addEventListener('click', handleDeleteJob);

            container.appendChild(jobBtn);
        });

    } catch (error) {
        if (!isSilent) {
            console.error('Error cargando los jobs:', error);
            container.innerHTML = `<p class="px-3 text-xs text-red-400">${t('error_loading_jobs')}</p>`;
        }
    }
}

/**
 * Maneja el clic en el botón de Ejecutar.
 */
async function handleRunJob(event) {
    event.stopPropagation(); // Evitar que dispare el modo edición
    const button = event.currentTarget;
    const jobId = button.dataset.id;

    // 1. Guardar el estado original del botón (clases y contenido HTML)
    const originalHtml = button.innerHTML;
    const originalClass = button.className;

    // 2. Deshabilitar y cambiar la UI a modo 'Cargando'
    button.disabled = true;
    button.className = 'btn-ejecutar flex items-center gap-1.5 px-2 py-1 rounded bg-brand-500/10 text-brand-500 opacity-70 cursor-not-allowed transition-all';
    button.innerHTML = `
        <svg class="animate-spin h-3 w-3 text-brand-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span class="text-[10px] font-semibold">${t('status_running')}</span>
    `;

    try {
        await api.runJob(jobId);
        showToast(`${t('toast_job_run_success')} (${jobId})`, 'success');
        
        const row = button.closest('.group');
        if (row) {
             const btnEdit = row.querySelector('.btn-edit-job');
             if (btnEdit) {
                 btnEdit.dataset.lastRunStatus = 'success';
             }
        }
        
        loadHistory();
    } catch (error) {
        console.error(`Error running job ${jobId}:`, error);
        showToast(`${t('toast_job_run_error')} (${jobId})`, 'error');
    } finally {
        button.disabled = false;
        button.className = originalClass;

        button.title = t('Ejecutar');
        button.innerHTML = '<i class="fa-solid fa-play text-[10px]"></i>';
    }
}

/**
 * 3.5 Obtener Estadísticas (Centro de Mando)
 */
async function loadStats(isSilent = false) {
    const elTotal = document.getElementById('stat-total-jobs');
    if (!elTotal) return;

    try {
        const stats = await api.getStats();
        elTotal.textContent = stats.total_jobs !== undefined ? stats.total_jobs : '0';
    } catch (error) {
        if (!isSilent) {
            console.error('Error cargando estadísticas:', error);
            elTotal.textContent = 'N/A';
        }
    }
}

/**
 * 4. Carga el historial desde la API y lo pinta en la barra lateral derecha.
 */
async function loadHistory(isSilent = false) {
    const container = document.getElementById('history-container');
    if (!container) return;

    try {
        const historyData = await api.getHistory();
        container.innerHTML = '';

        if (historyData.length === 0) {
            container.innerHTML = `<p class="text-slate-400 text-sm">${t('empty_history')}</p>`;
            return;
        }

        historyData.forEach(record => {
            const isSuccess = (record.status || '').toUpperCase() === 'SUCCESS';

            const statusClass = isSuccess
                ? 'bg-green-500/10 text-green-400 border-green-500/20'
                : 'bg-red-500/10 text-red-400 border-red-500/20';

            const borderClass = isSuccess
                ? 'border-slate-300 dark:border-slate-700 hover:border-brand-500'
                : 'border-red-500/30 hover:border-red-500';

            const rawDate = record.started_at || record.finished_at || record.timestamp || record.end_time || null;
            const dateStr = formatDateTimeSpain(rawDate);

            const runId = record._id || record.id || record.run_id || null;

            const historyItem = document.createElement('div');
            historyItem.className = `bg-slate-50 dark:bg-surface-800 border rounded-lg p-3 cursor-pointer transition-colors ${borderClass}`;
            if (runId) historyItem.dataset.runId = runId;

            historyItem.innerHTML = `
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-semibold text-slate-500 dark:text-slate-300">${dateStr}</span>
                    <div class="flex items-center gap-2">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold ${statusClass} border uppercase tracking-wide">
                            ${record.status}
                        </span>
                    </div>
                </div>
                <div class="flex items-center justify-between gap-4 text-xs text-slate-500 dark:text-slate-400">
                    <div class="flex items-center gap-1.5">
                        <i class="fa-solid fa-server"></i> Job ID: ${record.job_id || 'N/A'}
                    </div>
                    <div class="flex gap-2">
                        ${isSuccess ? `
                        <button class="btn-download px-2 py-1 rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500 hover:text-white text-[10px] font-medium transition-colors" data-run-id="${runId}" data-i18n="btn_download" onclick="event.stopPropagation(); window.open('/api/v1/history/run/${runId}/download', '_blank')">
                            <i class="fa-solid fa-download mr-1"></i> ${t('btn_download')}
                        </button>
                        <button class="btn-restore px-2 py-1 rounded bg-brand-500/10 text-brand-400 hover:bg-brand-500 hover:text-white text-[10px] font-medium transition-colors" data-run-id="${runId}" data-i18n="btn_restore" onclick="event.stopPropagation(); openRestoreConfirmModal('${runId}')">
                            <i class="fa-solid fa-rotate-left mr-1"></i> ${t('btn_restore')}
                        </button>` : ''}
                        <button class="btn-view-logs px-2 py-1 rounded bg-slate-500/10 text-slate-400 hover:bg-slate-500 hover:text-white text-[10px] font-medium transition-colors" data-run-id="${runId}" data-i18n="btn_view_logs">
                            <i class="fa-solid fa-terminal mr-1"></i> ${t('btn_view_logs')}
                        </button>
                    </div>
                </div>
                ${!isSuccess && record.error_message ? `<p class="text-[11px] text-red-400 truncate mt-2">Error: ${record.error_message}</p>` : ''}
            `;

            historyItem.addEventListener('click', (e) => {
                if (e.target.closest('.btn-view-logs') || e.target.closest('.btn-restore') || e.target.closest('.btn-download')) return;
                loadTerminalLogs(runId);
            });

            const logBtn = historyItem.querySelector('.btn-view-logs');
            if (logBtn) {
                logBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (runId) openLogViewer(runId, dateStr);
                });
            }

            container.appendChild(historyItem);
        });

    } catch (error) {
        if (!isSilent) {
            console.error('Error cargando historial:', error);
            container.innerHTML = `<p class="text-red-400 text-sm">${t('error_loading_history')}</p>`;
        }
    }
}

/**
 * Lógica del Modal de Confirmación de Restauración
 */
let currentRestoreRunId = null;

window.openRestoreConfirmModal = function (runId) {
    currentRestoreRunId = runId;
    const modal = document.getElementById('restoreConfirmModal');
    if (!modal) return;

    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0', 'scale-95');
        modal.classList.add('opacity-100', 'scale-100');
    }, 10);
};

window.closeRestoreConfirmModal = function () {
    const modal = document.getElementById('restoreConfirmModal');
    if (!modal) return;

    modal.classList.remove('opacity-100', 'scale-100');
    modal.classList.add('opacity-0', 'scale-95');

    setTimeout(() => {
        modal.classList.add('hidden');
        currentRestoreRunId = null;
    }, 300);
};

async function restoreBackup(runId) {
    if (!runId) {
        showToast(t('toast_restore_no_id'), 'error');
        return;
    }

    try {
        showToast(t('restore_in_progress'), 'info');
        if (typeof api !== 'undefined' && typeof api.restoreBackup === 'function') {
            await api.restoreBackup(runId);
        } else {
            const res = await fetch(`/api/v1/history/restore/${runId}`, { method: 'POST' });
            if (!res.ok) throw new Error(t('toast_restore_server_error'));
        }
        showToast(t('restore_success'), 'success');
    } catch (error) {
        console.error('Error al restaurar:', error);
        showToast(t('restore_error') + ' ' + error.message, 'error');
    }
}

/**
 * Inicializa la validación del formulario.
 */
/**
 * Payload para /utils/test-connection y /utils/test-db.
 * En edición sin contraseña en el input, envía job_id para usar la guardada.
 */
function buildDbUtilsPayload({ engine, host, port, user, password, database = '' }) {
    const body = {
        engine: engine || 'postgresql',
        host: host || 'localhost',
        port: port ? parseInt(port, 10) : 5432,
        user: user || 'postgres',
        password: password || '',
        database: database || ''
    };
    const jobId = currentEditingJobId
        || document.getElementById('createJobForm')?.dataset.editingId;
    if (jobId && !String(body.password).trim()) {
        body.job_id = parseInt(jobId, 10);
    }
    return body;
}

function isPasswordUnchangedInEditMode() {
    const form = document.getElementById('createJobForm');
    const passwordSavedUI = document.getElementById('passwordSavedUI');
    return Boolean(form && form.dataset.editingId && passwordSavedUI && !passwordSavedUI.classList.contains('hidden'));
}

function setPasswordEditMode(showSavedState) {
    const dbPassword = document.getElementById('dbPassword');
    const passwordSavedUI = document.getElementById('passwordSavedUI');
    const dbPasswordInputWrapper = document.getElementById('dbPasswordInputWrapper');
    if (!dbPassword || !passwordSavedUI || !dbPasswordInputWrapper) return;

    if (showSavedState) {
        passwordSavedUI.classList.remove('hidden');
        dbPasswordInputWrapper.classList.add('hidden');
        dbPassword.value = '';
        dbPassword.type = 'password';
        const icon = document.getElementById('dbPasswordToggleIcon');
        if (icon) icon.className = 'fa-solid fa-eye';
    } else {
        passwordSavedUI.classList.add('hidden');
        dbPasswordInputWrapper.classList.remove('hidden');
    }
}

function initPasswordFieldUX() {
    const dbPassword = document.getElementById('dbPassword');
    const btnToggle = document.getElementById('btnToggleDbPassword');
    const btnModify = document.getElementById('btnModifyPassword');
    const icon = document.getElementById('dbPasswordToggleIcon');

    if (btnToggle && dbPassword) {
        btnToggle.addEventListener('click', () => {
            const isHidden = dbPassword.type === 'password';
            dbPassword.type = isHidden ? 'text' : 'password';
            if (icon) {
                icon.className = isHidden ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
            }
        });
    }

    if (btnModify && dbPassword) {
        btnModify.addEventListener('click', () => {
            setPasswordEditMode(false);
            dbPassword.value = '';
            dbPassword.placeholder = '••••••••';
            dbPassword.focus();
        });
    }
}

function initJobFormValidation() {
    const form = document.getElementById('createJobForm');
    const btnSave = document.getElementById('btnSaveJob');
    const jobName = document.getElementById('jobName');
    const dbType = document.getElementById('dbType');
    const jobDesc = document.getElementById('jobDescription');
    const jobSched = document.getElementById('jobSchedule');
    const dbHost = document.getElementById('dbHost');
    const dbPort = document.getElementById('dbPort');
    const dbName = document.getElementById('dbName');
    const dbUser = document.getElementById('dbUser');
    const dbPassword = document.getElementById('dbPassword');

    initPasswordFieldUX();

    // Destinos
    const destType = document.getElementById('destType');
    const destLocalPath = document.getElementById('destLocalPath');
    const destGDriveFolderId = document.getElementById('destGDriveFolderId');
    const destGDriveFolderName = document.getElementById('destGDriveFolderName');
    const destLocalPathContainer = document.getElementById('destLocalPathContainer');
    const destGDriveContainer = document.getElementById('destGDriveContainer');
    const dbFilePathContainer = document.getElementById('dbFilePathContainer');
    const dbCredentialsContainer = document.getElementById('dbCredentialsContainer');
    const networkDetails = document.querySelector('details.group');

    form.addEventListener('input', () => { isFormDirty = true; });
    form.addEventListener('change', () => { isFormDirty = true; });

    const btnNewJobSidebar = document.getElementById('btnNewJobSidebar');
    if (btnNewJobSidebar) {
        btnNewJobSidebar.addEventListener('click', async () => {
            if (isFormDirty) {
                const confirmDiscard = await showGenericConfirm(t('confirm_discard_title'), t('confirm_discard_new'), t('btn_yes_discard'));
                if (!confirmDiscard) return;
                isFormDirty = false;
            }
            resetFormToCreateMode();
            const formEl = document.getElementById('createJobForm');
            if (formEl) formEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    const scheduleIntervalContainer = document.getElementById('scheduleIntervalContainer');
    const scheduleCronContainer = document.getElementById('scheduleCronContainer');
    const scheduleTimeContainer = document.getElementById('scheduleTimeContainer');
    const scheduleDayOfWeekContainer = document.getElementById('scheduleDayOfWeekContainer');
    const scheduleDayOfMonthContainer = document.getElementById('scheduleDayOfMonthContainer');
    const jobScheduleInterval = document.getElementById('jobScheduleInterval');
    const jobScheduleCron = document.getElementById('jobScheduleCron');
    const jobScheduleHour = document.getElementById('jobScheduleHour');
    const jobScheduleMinute = document.getElementById('jobScheduleMinute');
    const jobScheduleDayOfWeek = document.getElementById('jobScheduleDayOfWeek');
    const jobScheduleDayOfMonth = document.getElementById('jobScheduleDayOfMonth');

    if (!form || !btnSave) return;

    form.addEventListener('submit', (ev) => ev.preventDefault());

    if (jobSched) {
        jobSched.addEventListener('change', () => {
            const s = jobSched.value;
            [scheduleIntervalContainer, scheduleCronContainer, scheduleTimeContainer,
                scheduleDayOfWeekContainer, scheduleDayOfMonthContainer].forEach(el => {
                    if (el) el.classList.add('hidden');
                });

            if (s === 'interval' && scheduleIntervalContainer) scheduleIntervalContainer.classList.remove('hidden');
            else if (s === 'cron' && scheduleCronContainer) scheduleCronContainer.classList.remove('hidden');
            else if (s === 'daily' && scheduleTimeContainer) scheduleTimeContainer.classList.remove('hidden');
            else if (s === 'weekly') {
                if (scheduleTimeContainer) scheduleTimeContainer.classList.remove('hidden');
                if (scheduleDayOfWeekContainer) scheduleDayOfWeekContainer.classList.remove('hidden');
            }
            else if (s === 'monthly') {
                if (scheduleTimeContainer) scheduleTimeContainer.classList.remove('hidden');
                if (scheduleDayOfMonthContainer) scheduleDayOfMonthContainer.classList.remove('hidden');
            }
        });
    }

    const jobTypeCards = document.querySelectorAll('.job-type-card');
    const dbConfigContainer = document.getElementById('dbConfigContainer');
    const jobOptionsContainer = document.getElementById('jobOptionsContainer');
    let currentJobType = 'db'; // db, folder, sync

    jobTypeCards.forEach(card => {
        card.addEventListener('click', () => {
            const wizardStep2 = document.getElementById('wizardStep2');
            clearAllErrors(wizardStep2 || document);
            jobTypeCards.forEach(c => c.classList.remove('border-brand-500', 'bg-brand-50', 'dark:bg-brand-500/10', 'ring-1', 'ring-brand-500'));
            card.classList.add('border-brand-500', 'bg-brand-50', 'dark:bg-brand-500/10', 'ring-1', 'ring-brand-500');
            currentJobType = card.dataset.jobType;

            if (currentJobType === 'db') {
                dbConfigContainer.classList.remove('hidden');
                dbFilePathContainer.classList.add('hidden');
                if (dbCredentialsContainer) dbCredentialsContainer.classList.remove('hidden');
                jobOptionsContainer.classList.remove('hidden');
                // Trigger change to update credentials visibility based on selected engine
                if (dbType) dbType.dispatchEvent(new Event('change'));
            } else if (currentJobType === 'folder') {
                dbConfigContainer.classList.add('hidden');
                if (dbCredentialsContainer) dbCredentialsContainer.classList.add('hidden');
                dbFilePathContainer.classList.remove('hidden');
                jobOptionsContainer.classList.remove('hidden');
            } else if (currentJobType === 'sync') {
                dbConfigContainer.classList.add('hidden');
                if (dbCredentialsContainer) dbCredentialsContainer.classList.add('hidden');
                dbFilePathContainer.classList.remove('hidden');
                jobOptionsContainer.classList.add('hidden'); // Ocultar retención y compresión
            }
        });
    });

    // Inicializar seleccionando el primero por defecto
    if (jobTypeCards.length > 0) {
        jobTypeCards[0].click();
    }

    if (dbType) {
        dbType.addEventListener('change', () => {
            if (currentJobType !== 'db') return;
            const t = dbType.value;
            if (t === 'sqlite' || t === 'mdb') {
                if (dbCredentialsContainer) dbCredentialsContainer.classList.remove('hidden');
                if (networkDetails) networkDetails.classList.add('hidden');
                if (dbFilePathContainer) dbFilePathContainer.classList.add('hidden');
            } else {
                if (dbCredentialsContainer) dbCredentialsContainer.classList.remove('hidden');
                if (networkDetails) networkDetails.classList.remove('hidden');
                if (dbFilePathContainer) dbFilePathContainer.classList.add('hidden');
            }

            if (t === 'postgresql') {
                if (dbPort) dbPort.value = 5432;
                if (dbUser) dbUser.value = 'postgres';
            } else if (t === 'sqlserver') {
                if (dbPort) dbPort.value = 1433;
                if (dbUser) dbUser.value = 'sa';
            } else if (t === 'mysql') {
                if (dbPort) dbPort.value = 3306;
                if (dbUser) dbUser.value = 'root';
            }
        });
    }

    if (destType && destLocalPathContainer && destGDriveContainer) {
        destType.addEventListener('change', () => {
            if (destType.value === 'google_drive') {
                destLocalPathContainer.classList.add('hidden');
                destGDriveContainer.classList.remove('hidden');
            } else {
                destLocalPathContainer.classList.remove('hidden');
                destGDriveContainer.classList.add('hidden');
            }
        });
    }

    form.addEventListener('click', (e) => {
        if (e.target.closest('#btnCancelEdit')) {
            isFormDirty = false;
            resetFormToCreateMode();
        }
    });

    const btnTestConnection = document.getElementById('btn-test-connection') || document.getElementById('btnTestConnection');
    const btnListDbs = document.getElementById('btn-list-dbs');

    if (btnListDbs) {
        btnListDbs.addEventListener('click', async () => {
            const originalHtml = btnListDbs.innerHTML;
            btnListDbs.disabled = true;
            btnListDbs.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Cargando...`;
            try {
                const engine = document.getElementById('dbType') ? document.getElementById('dbType').value : 'postgresql';
                const hostVal = document.getElementById('dbHost') ? document.getElementById('dbHost').value.trim() : '';
                const portVal = document.getElementById('dbPort') ? document.getElementById('dbPort').value : '';
                const userVal = document.getElementById('dbUser') ? document.getElementById('dbUser').value.trim() : '';
                const passwordVal = document.getElementById('dbPassword') ? document.getElementById('dbPassword').value : '';

                const response = await fetch('/api/v1/utils/test-db', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(buildDbUtilsPayload({
                        engine,
                        host: hostVal,
                        port: portVal,
                        user: userVal,
                        password: passwordVal,
                        database: ''
                    }))
                });

                const data = await response.json();
                if (response.ok && Array.isArray(data.databases)) {
                    const dbNameSelect = document.getElementById('dbName');
                    if (dbNameSelect) {
                        dbNameSelect.innerHTML = data.databases.map(db => `<option value="${db}">${db}</option>`).join('');
                        showToast(`Se encontraron ${data.databases.length} bases de datos.`, 'success');
                    }
                } else {
                    showToast('Error al listar bases de datos: ' + (data.detail || 'Error desconocido'), 'error');
                }
            } catch (error) {
                showToast(`❌ Error de red: ${error.message}`, 'error');
            } finally {
                btnListDbs.disabled = false;
                btnListDbs.innerHTML = originalHtml;
            }
        });
    }

    if (btnTestConnection) {
        btnTestConnection.addEventListener('click', async () => {
            const originalHtml = btnTestConnection.innerHTML;
            btnTestConnection.disabled = true;
            btnTestConnection.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${t('status_testing') || 'Probando...'}`;

            try {
                const engine = document.getElementById('dbType') ? document.getElementById('dbType').value : 'postgresql';
                const hostVal = document.getElementById('dbHost') ? document.getElementById('dbHost').value.trim() : '';
                const portVal = document.getElementById('dbPort') ? document.getElementById('dbPort').value : '';
                const userVal = document.getElementById('dbUser') ? document.getElementById('dbUser').value.trim() : '';
                const passwordVal = document.getElementById('dbPassword') ? document.getElementById('dbPassword').value : '';
                const databaseVal = document.getElementById('dbName') ? document.getElementById('dbName').value.trim() : '';

                const response = await fetch('/api/v1/utils/test-connection', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(buildDbUtilsPayload({
                        engine,
                        host: hostVal,
                        port: portVal,
                        user: userVal,
                        password: passwordVal,
                        database: databaseVal
                    }))
                });

                const errorData = await response.json();

                if (response.ok) {
                    showToast(t('toast_connection_ok'), 'success');
                } else {
                    let errorMsg = errorData.detail || t('toast_connection_error');
                    if (Array.isArray(errorMsg)) {
                        errorMsg = errorMsg.map(e => e.msg).join(', ');
                    } else if (typeof errorMsg === 'object') {
                        errorMsg = JSON.stringify(errorMsg);
                    }
                    showToast(`❌ ${errorMsg}`, 'error');
                }
            } catch (error) {
                showToast(`❌ ${t('error_network')}: ${error.message}`, 'error');
            } finally {
                btnTestConnection.disabled = false;
                btnTestConnection.innerHTML = originalHtml;
            }
        });
    }

    btnSave.addEventListener('click', async (e) => {
        e.preventDefault();
        if (btnSave.dataset.saving === 'true') return;

        clearAllErrors(form || document);
        let isValid = true;

        // --- BUG FIX 1: Leer el tipo de tarea desde la tarjeta activa (no desde el select) ---
        const activeJobTypeCard = document.querySelector('.job-type-card.border-brand-500');
        const finalJobType = activeJobTypeCard ? activeJobTypeCard.dataset.jobType : 'db';

        if (jobName) clearErrors(jobName);
        if (dbType) clearErrors(dbType);

        if (!jobName || jobName.value.trim() === '') {
            showError(jobName, t('error_field_required'));
            isValid = false;
        }

        // Solo validar el motor si es tipo 'db'
        if (finalJobType === 'db' && dbType && dbType.value.trim() === '') {
            showError(dbType, t('error_select_engine'));
            isValid = false;
        }

        const dbFilePathEl = document.getElementById('dbFilePath');
        const isFileEngine = finalJobType === 'db' && dbType && (dbType.value === 'sqlite' || dbType.value === 'mdb');
        const requiresServerAuth = finalJobType === 'db' && !isFileEngine;

        if (requiresServerAuth) {
            if (!dbHost || !dbHost.value.trim()) {
                showError(dbHost, t('error_field_required') || 'Host obligatorio');
                isValid = false;
            } else {
                clearErrors(dbHost);
            }

            if (!dbPort || !dbPort.value.trim()) {
                showError(dbPort, t('error_field_required') || 'Puerto obligatorio');
                isValid = false;
            } else {
                clearErrors(dbPort);
            }

            if (!dbUser || !dbUser.value.trim()) {
                showError(dbUser, t('error_field_required') || 'Usuario obligatorio');
                isValid = false;
            } else {
                clearErrors(dbUser);
            }

            if (!isPasswordUnchangedInEditMode()) {
                if (!dbPassword || !dbPassword.value.trim()) {
                    showError(dbPassword, t('error_field_required') || 'Contraseña obligatoria');
                    isValid = false;
                } else {
                    clearErrors(dbPassword);
                }
            } else if (dbPassword) {
                clearErrors(dbPassword);
            }

            const selectedDbsForSave = dbName && dbName.tagName.toLowerCase() === 'select'
                ? Array.from(dbName.selectedOptions).map(opt => opt.value).filter(Boolean)
                : [];
            if (!dbName || selectedDbsForSave.length === 0) {
                showError(dbName, t('error_field_required') || 'Selecciona al menos una BD');
                isValid = false;
            } else {
                clearErrors(dbName);
            }
        }

        if (finalJobType === 'folder' || finalJobType === 'sync') {
            const pathValue = dbFilePathEl ? dbFilePathEl.value.trim() : '';
            if (!pathValue) {
                showError(dbFilePathEl, t('error_path_required') || 'Especifica la ruta de origen');
                isValid = false;
            } else {
                clearErrors(dbFilePathEl);
            }
        }

        if (!isValid) {
            abortSaveValidation(btnSave);
            return;
        }

        const destType = document.getElementById('destType');
        const destLocalPath = document.getElementById('destLocalPath');
        if (destType && destType.value === 'local') {
            const destVal = destLocalPath ? destLocalPath.value.trim() : '';
            if (!destVal) {
                showValidationToast(t('error_path_required') || 'Debes especificar la ruta de destino');
                abortSaveValidation(btnSave);
                return;
            }
        } else if (destType && destType.value === 'google_drive') {
            const folderName = destGDriveFolderName ? destGDriveFolderName.value.trim() : '';
            if (!folderName) {
                showValidationToast('Selecciona una carpeta de Google Drive antes de guardar.');
                abortSaveValidation(btnSave);
                return;
            }
        }

        const editingId = form.dataset.editingId || null;

        let finalDbName = null;
        if (dbName && dbName.tagName.toLowerCase() === 'select' && dbName.multiple) {
            const selectedOptions = Array.from(dbName.selectedOptions).map(opt => opt.value);
            finalDbName = selectedOptions.length > 0 ? selectedOptions.join(',') : null;
        } else if (dbName) {
            finalDbName = dbName.value.trim() || null;
        }

        if (finalJobType === 'folder' || finalJobType === 'sync') {
            const pathValue = dbFilePathEl ? dbFilePathEl.value.trim() : '';
            if (!pathValue) {
                showValidationToast(t('error_path_required') || 'Especifica la ruta de origen');
                abortSaveValidation(btnSave);
                return;
            }
            finalDbName = pathValue;
        }

        let finalScheduleType = jobSched ? jobSched.value : 'manual';
        let finalCron = jobScheduleCron ? jobScheduleCron.value.trim() || null : null;
        let finalInterval = jobScheduleInterval ? parseInt(jobScheduleInterval.value) || null : null;

        if (finalScheduleType === 'daily' || finalScheduleType === 'weekly' || finalScheduleType === 'monthly') {
            const timeVal = getScheduleTimeValue();
            const scheduleTimeContainer = document.getElementById('scheduleTimeContainer');
            if (!timeVal) {
                showValidationToast('Debes indicar una hora para la programación seleccionada.');
                if (scheduleTimeContainer) showError(scheduleTimeContainer, t('error_field_required') || 'Obligatorio');
                abortSaveValidation(btnSave);
                return;
            } else if (scheduleTimeContainer) {
                clearErrors(scheduleTimeContainer);
            }
            const [hourStr, minStr] = timeVal.split(':');
            const hour = parseInt(hourStr) || 0;
            const min = parseInt(minStr) || 0;

            if (finalScheduleType === 'daily') {
                finalCron = `${min} ${hour} * * *`;
            } else if (finalScheduleType === 'weekly') {
                const dow = jobScheduleDayOfWeek ? jobScheduleDayOfWeek.value : '0';
                if (!dow && jobScheduleDayOfWeek) {
                    showError(jobScheduleDayOfWeek, t('error_field_required') || 'Obligatorio');
                    abortSaveValidation(btnSave);
                    return;
                } else if (jobScheduleDayOfWeek) {
                    clearErrors(jobScheduleDayOfWeek);
                }
                finalCron = `${min} ${hour} * * ${dow}`;
            } else if (finalScheduleType === 'monthly') {
                const dom = jobScheduleDayOfMonth ? jobScheduleDayOfMonth.value : '';
                const domNum = parseInt(dom, 10);
                if (!dom || Number.isNaN(domNum) || domNum < 1 || domNum > 28) {
                    if (jobScheduleDayOfMonth) showError(jobScheduleDayOfMonth, t('error_field_required') || 'Selecciona un día del mes');
                    abortSaveValidation(btnSave);
                    return;
                } else if (jobScheduleDayOfMonth) {
                    clearErrors(jobScheduleDayOfMonth);
                }
                finalCron = `${min} ${hour} ${dom} * *`;
            }
            finalScheduleType = 'cron';
            finalInterval = null;
        }

        // finalJobType ya está declarado arriba; calculamos el db_type definitivo
        let finalDbType = (dbType && dbType.value) ? dbType.value : 'postgresql';
        if (finalJobType === 'folder') finalDbType = 'folder';
        if (finalJobType === 'sync') finalDbType = 'sync';

        // --- BUG FIX 3: Para sync, forzar valores seguros (sin retención ni compresión) ---
        const isSync = finalJobType === 'sync';
        const retentionEl = document.getElementById('jobRetention');
        const compressEl = document.getElementById('compressBackup');

        let retentionVal = 0;
        if (retentionEl && retentionEl.value.trim() !== '') {
            retentionVal = parseInt(retentionEl.value, 10);
            if (isNaN(retentionVal)) retentionVal = 0;
        }

        const jobData = {
            name: jobName.value.trim(),
            description: jobDesc ? jobDesc.value.trim() || null : null,
            db_type: finalDbType,
            db_host: dbHost ? dbHost.value.trim() || null : null,
            db_port: dbPort ? parseInt(dbPort.value) || null : null,
            db_name: finalDbName,
            db_user: dbUser ? dbUser.value.trim() || null : null,
            db_password: (!isPasswordUnchangedInEditMode() && dbPassword && dbPassword.value.trim())
                ? dbPassword.value
                : undefined,
            schedule: finalScheduleType,
            schedule_interval_minutes: finalInterval,
            schedule_cron: finalCron,
            dest_type: destType ? destType.value : 'local',
            dest_local_path: destLocalPath && destLocalPath.value.trim() ? destLocalPath.value.trim() : null,
            dest_gdrive_folder_id: destGDriveFolderId && destGDriveFolderId.value.trim() ? destGDriveFolderId.value.trim() : null,
            dest_gdrive_folder_name: destGDriveFolderName && destGDriveFolderName.value.trim() ? destGDriveFolderName.value.trim() : null,
            dest_retention_days: isSync ? null : retentionVal,
            compress: isSync ? false : (compressEl ? compressEl.checked : false),
        };
        
        Object.keys(jobData).forEach(k => jobData[k] === undefined && delete jobData[k]);

        console.log('--- INTENTANDO GUARDAR ---');
        console.log('Payload:', jobData);

        btnSave.dataset.saving = 'true';
        btnSave.disabled = true;
        btnSave.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${t('status_saving')}`;

        try {
            if (editingId) {
                await api.updateJob(editingId, jobData);
                showToast(`${t('toast_job_updated')} «${jobData.name}»`, 'success');
                resetFormToCreateMode();
            } else {
                await api.createJob(jobData);
                showToast(t('toast_job_created'), 'success');
                // --- BUG FIX 4: Resetear el wizard al paso 1 tras crear ---
                form.reset();
                if (typeof showWizardStep === 'function') showWizardStep(1);
                const jobTypeCards = document.querySelectorAll('.job-type-card');
                if (jobTypeCards.length > 0) jobTypeCards[0].click();
            }
            loadJobs();
        } catch (error) {
            // --- BUG FIX 5: Mostrar detalle del error 422/500 del backend ---
            let errMsg = t('toast_job_save_error');
            if (error && error.message) errMsg = error.message;
            console.error('[SolbaBackups] Error al guardar tarea:', error);
            // Intentar extraer detalle del error de red
            if (error && error.apiDetail) {
                console.error('[SolbaBackups] Detalle API:', JSON.stringify(error.apiDetail, null, 2));
                if (Array.isArray(error.apiDetail)) {
                    errMsg = error.apiDetail.map(e => `${e.loc?.join('.')}: ${e.msg}`).join(' | ');
                } else if (typeof error.apiDetail === 'string') {
                    errMsg = error.apiDetail;
                }
            }
            showToast(`❌ ${errMsg}`, 'error');
        } finally {
            delete btnSave.dataset.saving;
            resetSaveButtonState(btnSave);
            isFormDirty = false;
        }
    });
}

async function handleEditJob(event) {
    const btn = event.currentTarget;
    if (isFormDirty) {
        const confirmDiscard = await showGenericConfirm(t('confirm_discard_title'), t('confirm_discard_edit'), t('btn_yes_discard'));
        if (!confirmDiscard) return;
        isFormDirty = false;
    }

    const id = btn.dataset.id;
    const name = btn.dataset.name;
    const sch = btn.dataset.schedule;
    const folderName = btn.dataset.destGdriveFolderName || '';
    const extra = {
        db_type: btn.dataset.dbType || '',
        db_host: btn.dataset.dbHost || '',
        db_port: btn.dataset.dbPort || '',
        db_name: btn.dataset.dbName || '',
        db_user: btn.dataset.dbUser || '',
        description: btn.dataset.description || '',
        schedule_type: btn.dataset.schedule || 'manual',
        schedule_interval_minutes: btn.dataset.scheduleInterval || '',
        schedule_cron: btn.dataset.scheduleCron || '',
        dest_type: btn.dataset.destType || 'local',
        dest_local_path: btn.dataset.destLocalPath || '',
        dest_gdrive_folder_id: btn.dataset.destGdriveFolderId || '',
        dest_gdrive_folder_name: folderName,
        dest_retention_days: btn.dataset.destRetentionDays || '0',
        compress: btn.dataset.compress === 'true',
    };

    setFormEditMode(id, name, extra, sch);

    const form = document.getElementById('createJobForm');
    if (form) form.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function handleDeleteJob(event) {
    const btn = event.currentTarget;
    const jobId = btn.dataset.id;
    const name = btn.dataset.name || `${t('label_job')} ${jobId}`;
    showDeleteConfirm(jobId, name);
}

function setFormEditMode(id, name, extra = {}, schedule) {
    const form = document.getElementById('createJobForm');
    const jobName = document.getElementById('jobName');
    const dbType = document.getElementById('dbType');
    const jobDesc = document.getElementById('jobDescription');
    const jobSched = document.getElementById('jobSchedule');
    const dbHost = document.getElementById('dbHost');
    const dbPort = document.getElementById('dbPort');
    const dbName = document.getElementById('dbName');
    const dbUser = document.getElementById('dbUser');
    const dbPassword = document.getElementById('dbPassword');
    const btnSave = document.getElementById('btnSaveJob');
    const heading = form ? form.querySelector('h3') : null;

    if (!form) return;

    form.dataset.editingId = id;
    currentEditingJobId = id;

    if (jobName) jobName.value = name;
    if (dbType) dbType.value = extra.db_type || '';
    if (jobDesc) jobDesc.value = extra.description || '';
    if (jobSched) jobSched.value = extra.schedule_type || 'manual';
    if (dbHost) dbHost.value = extra.db_host || '';
    if (dbPort) dbPort.value = extra.db_port || '';
    if (dbUser) dbUser.value = extra.db_user || '';
    if (dbPassword) {
        dbPassword.value = '';
        dbPassword.placeholder = t('ph_password_saved') || '••••••••';
    }
    setPasswordEditMode(true);

    const dbFilePathEl = document.getElementById('dbFilePath');
    if (extra.db_type === 'sqlite' || extra.db_type === 'folder' || extra.db_type === 'mdb' || extra.db_type === 'sync') {
        if (dbFilePathEl) dbFilePathEl.value = extra.db_name || '';
        if (dbName) {
            if (dbName.tagName.toLowerCase() === 'select') dbName.innerHTML = '';
            else dbName.value = '';
        }
    } else {
        if (dbName) {
            if (dbName.tagName.toLowerCase() === 'select' && dbName.multiple) {
                const parts = (extra.db_name || '').split(',');
                dbName.innerHTML = parts.map(p => p.trim() ? `<option value="${p.trim()}" selected>${p.trim()}</option>` : '').join('');
            } else {
                dbName.value = extra.db_name || '';
            }
        }
        if (dbFilePathEl) dbFilePathEl.value = '';
    }

    let displaySchedule = schedule || 'manual';
    let displayCron = extra.schedule_cron || '';
    let displayTime = '';
    let displayDow = '';
    let displayDom = '';

    if (displaySchedule === 'cron' && displayCron) {
        const parts = displayCron.split(' ');
        if (parts.length === 5) {
            const [min, hour, dom, mon, dow] = parts;
            if (dom === '*' && mon === '*' && dow === '*') {
                displaySchedule = 'daily';
                displayTime = `${hour.padStart(2, '0')}:${min.padStart(2, '0')}`;
            } else if (dom === '*' && mon === '*' && dow !== '*') {
                displaySchedule = 'weekly';
                displayTime = `${hour.padStart(2, '0')}:${min.padStart(2, '0')}`;
                displayDow = dow;
            } else if (dom !== '*' && mon === '*' && dow === '*') {
                displaySchedule = 'monthly';
                displayTime = `${hour.padStart(2, '0')}:${min.padStart(2, '0')}`;
                displayDom = dom;
            }
        }
    }

    if (jobSched) jobSched.value = displaySchedule;

    const jobScheduleInterval = document.getElementById('jobScheduleInterval');
    const jobScheduleCron = document.getElementById('jobScheduleCron');
    const jobScheduleDayOfWeek = document.getElementById('jobScheduleDayOfWeek');
    const jobScheduleDayOfMonth = document.getElementById('jobScheduleDayOfMonth');

    initScheduleTimeSelects();
    if (jobScheduleInterval) jobScheduleInterval.value = extra.schedule_interval_minutes || '';
    if (jobScheduleCron) jobScheduleCron.value = displaySchedule === 'cron' ? displayCron : '';
    if (displayTime) setScheduleTimeValue(displayTime);
    if (jobScheduleDayOfWeek && displayDow) jobScheduleDayOfWeek.value = displayDow;
    if (jobScheduleDayOfMonth && displayDom) jobScheduleDayOfMonth.value = displayDom;

    const destType = document.getElementById('destType');
    const destLocalPath = document.getElementById('destLocalPath');
    const destGDriveFolderId = document.getElementById('destGDriveFolderId');
    const destGDriveFolderName = document.getElementById('destGDriveFolderName');
    if (destType) destType.value = extra.dest_type || 'local';
    if (destLocalPath) destLocalPath.value = extra.dest_local_path || '';
    if (destGDriveFolderId) destGDriveFolderId.value = extra.dest_gdrive_folder_id || '';
    if (destGDriveFolderName) destGDriveFolderName.value = extra.dest_gdrive_folder_name || '';

    const jobRetention = document.getElementById('jobRetention');
    if (jobRetention) jobRetention.value = extra.dest_retention_days !== undefined ? extra.dest_retention_days : '0';

    const compressBackup = document.getElementById('compressBackup');
    if (compressBackup) compressBackup.checked = extra.compress !== undefined ? extra.compress : false;

    if (dbType) dbType.dispatchEvent(new Event('change'));
    if (destType) destType.dispatchEvent(new Event('change'));
    if (jobSched) jobSched.dispatchEvent(new Event('change'));

    if (heading) {
        heading.innerHTML = `✏️ Editando Tarea: ${name}`;
    }

    form.classList.remove('border-slate-200', 'dark:border-slate-800');
    form.classList.add('ring-4', 'ring-orange-500/50', 'border-orange-500');

    let btnCancelEditTop = document.getElementById('btnCancelEditTop');
    if (btnCancelEditTop) {
        btnCancelEditTop.classList.remove('hidden');
    }

    const btnSaveText = document.getElementById('btnSaveJobText');
    if (btnSaveText) {
        btnSaveText.innerHTML = `Actualizar Tarea`;
    }

    if (btnSave) {
        btnSave.classList.replace('bg-emerald-500', 'bg-orange-500');
        btnSave.classList.replace('hover:bg-emerald-600', 'hover:bg-orange-600');
        // also handle old brand classes just in case
        btnSave.classList.replace('bg-brand-500', 'bg-orange-500');
        btnSave.classList.replace('hover:bg-brand-600', 'hover:bg-orange-600');
    }
    
    // Also simulate clicking the right jobTypeCard
    const jobTypeCards = document.querySelectorAll('.job-type-card');
    let targetType = 'db';
    if (extra.db_type === 'folder') targetType = 'folder';
    if (extra.db_type === 'sync') targetType = 'sync';
    
    jobTypeCards.forEach(c => {
        if (c.dataset.jobType === targetType) {
            c.click();
        }
    });

    const cancelBtn = document.getElementById('btnCancelEdit');
    if (cancelBtn) cancelBtn.classList.remove('hidden');

    // Reset to step 1 when editing
    if (typeof showWizardStep === 'function') {
        showWizardStep(1);
    }
}

function resetFormToCreateMode() {
    const form = document.getElementById('createJobForm');
    const btnSaveText = document.getElementById('btnSaveJobText');
    const dbPassword = document.getElementById('dbPassword');
    const heading = document.getElementById('formTitle');
    const btnCancelEditTop = document.getElementById('btnCancelEditTop');

    if (!form) return;

    form.reset();
    setScheduleTimeValue('02:00');
    const domSel = document.getElementById('jobScheduleDayOfMonth');
    if (domSel) domSel.value = '1';
    if (dbPassword) {
        dbPassword.value = '';
        dbPassword.placeholder = '••••••••';
        dbPassword.type = 'password';
    }
    setPasswordEditMode(false);
    delete form.dataset.editingId;
    currentEditingJobId = null;
    delete form.dataset.editingSchedule;

    if (heading) heading.textContent = t('title_new_backup_job') || 'Crear Nueva Tarea';

    if (btnSaveText) {
        btnSaveText.innerHTML = `${t('btn_save_job') || 'Crear Tarea'}`;
    }
    
    const btnSave = document.getElementById('btnSaveJob');
    if (btnSave) {
        btnSave.classList.replace('bg-orange-500', 'bg-emerald-500');
        btnSave.classList.replace('hover:bg-orange-600', 'hover:bg-emerald-600');
    }

    const cancelBtn = document.getElementById('btnCancelEdit');
    if (cancelBtn) cancelBtn.classList.add('hidden');
    
    if (btnCancelEditTop) btnCancelEditTop.classList.add('hidden');

    form.classList.remove('ring-4', 'ring-orange-500/50', 'border-orange-500');
    form.classList.add('border-slate-200', 'dark:border-slate-800');
    
    const badge = form.querySelector('#edit-mode-badge');
    if (badge) badge.remove();

    document.querySelectorAll('.discovery-card').forEach(c => {
        c.classList.remove('border-brand-500', 'bg-brand-500/10', 'dark:bg-brand-500/10', 'bg-brand-500/5');
        c.classList.add('border-slate-300', 'dark:border-slate-700', 'bg-white', 'dark:bg-surface-950');
    });

    const jobTypeCards = document.querySelectorAll('.job-type-card');
    if (jobTypeCards.length > 0) {
        jobTypeCards[0].click();
    }

    isFormDirty = false;
    
    // Reset to step 1
    if (typeof showWizardStep === 'function') {
        showWizardStep(1);
    }
}

function showDeleteConfirm(jobId, name) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    if (document.getElementById('toast-delete-confirm')) return;

    const toast = document.createElement('div');
    toast.id = 'toast-delete-confirm';
    toast.className = 'toast';
    toast.style.cssText = [
        'background:#1e293b',
        'border:1px solid #ef4444',
        'min-width:320px',
        'flex-direction:column',
        'gap:0.75rem',
        'align-items:flex-start'
    ].join(';');
    toast.style.pointerEvents = 'auto';

    toast.innerHTML = `
        <div class="flex items-start gap-3">
            <i class="fa-solid fa-triangle-exclamation text-red-400 text-lg mt-0.5"></i>
            <div>
                <p class="text-white text-sm font-semibold">${t('confirm_delete_title')}</p>
                <p class="text-slate-400 text-xs mt-0.5 leading-relaxed">
                    «${name}» ${t('confirm_delete_body')}
                </p>
            </div>
        </div>
        <div class="flex gap-2 w-full">
            <button id="toast-delete-ok"
                    class="flex-1 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold py-1.5 rounded-lg transition-colors">
                <i class="fa-solid fa-trash-can mr-1"></i> ${t('btn_confirm_delete')}
            </button>
            <button id="toast-delete-cancel"
                    class="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold py-1.5 rounded-lg transition-colors">
                ${t('btn_cancel')}
            </button>
        </div>
    `;

    container.appendChild(toast);

    const removeToast = () => {
        toast.classList.add('hiding');
        toast.addEventListener('animationend', () => toast.remove(), { once: true });
    };

    toast.querySelector('#toast-delete-ok').addEventListener('click', async () => {
        removeToast();
        try {
            await api.deleteJob(jobId);
            showToast(`${t('toast_job_deleted')} «${name}»`, 'success');
            loadJobs();
        } catch (err) {
            console.error('Error deleting job:', err);
            showToast(`${t('toast_job_delete_error')} «${name}»`, 'error');
        }
    });

    toast.querySelector('#toast-delete-cancel').addEventListener('click', removeToast);

    setTimeout(removeToast, 8000);
}

function showError(inputElement, message) {
    if (!inputElement || !inputElement.parentElement) return;
    clearErrors(inputElement);
    inputElement.classList.add('input-error');
    const errorText = document.createElement('div');
    errorText.className = 'error-message text-red-500 text-xs mt-1';
    errorText.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> ${message}`;
    inputElement.parentElement.appendChild(errorText);
}

function clearErrors(inputElement) {
    if (!inputElement || !inputElement.parentElement) return;
    inputElement.classList.remove('input-error');
    const existingError = inputElement.parentElement.querySelector('.error-message');
    if (existingError) {
        existingError.remove();
    }
}

function clearAllErrors(scope = document) {
    if (!scope) return;
    scope.querySelectorAll('.input-error').forEach((el) => el.classList.remove('input-error'));
    scope.querySelectorAll('.error-message').forEach((el) => el.remove());
}

function setupPolling() {
    setInterval(async () => {
        try {
            await Promise.all([
                loadJobs(true),
                loadHistory(true),
                loadStats(true)
            ]);
        } catch (error) {
            console.warn('Polling error (silenciado):', error);
        }
    }, 8000);
}


function dismissToasts(type = null) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    container.querySelectorAll('.toast').forEach((toast) => {
        if (!type || toast.classList.contains(`toast-${type}`)) {
            toast.remove();
        }
    });
}

function showValidationToast(message) {
    showToast(message, 'error', { replace: true });
}

function resetSaveButtonState(btnSave) {
    if (!btnSave) return;
    const form = document.getElementById('createJobForm');
    const editingId = form && form.dataset.editingId;
    delete btnSave.dataset.saving;
    btnSave.disabled = false;
    const label = editingId
        ? (t('btn_update_job') || 'Actualizar Tarea')
        : (t('btn_save_job') || 'Finalizar y Guardar');
    btnSave.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> <span id="btnSaveJobText" data-i18n="btn_save_job">${label}</span>`;
    if (editingId) {
        btnSave.classList.remove('bg-emerald-500', 'hover:bg-emerald-600', 'bg-brand-500', 'hover:bg-brand-600');
        btnSave.classList.add('bg-orange-500', 'hover:bg-orange-600');
    } else {
        btnSave.classList.remove('bg-orange-500', 'hover:bg-orange-600');
        btnSave.classList.add('bg-emerald-500', 'hover:bg-emerald-600');
    }
}

function abortSaveValidation(btnSave) {
    resetSaveButtonState(btnSave);
    if (!btnSave) return;
    btnSave.classList.add('animate-shake');
    setTimeout(() => btnSave.classList.remove('animate-shake'), 400);
}

function showToast(message, type = 'success', options = {}) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    if (options.replace && type) {
        dismissToasts(type);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type} bg-white dark:bg-[#1e293b] text-slate-800 dark:text-white border shadow-lg`;
    toast.style.pointerEvents = 'auto';
    if (type === 'success') toast.classList.add('border-green-500');
    else toast.classList.add('border-red-500');

    const icon = type === 'success'
        ? '<i class="fa-solid fa-circle-check text-lg text-green-500"></i>'
        : '<i class="fa-solid fa-circle-exclamation text-lg text-red-500"></i>';

    toast.innerHTML = `
        ${icon}
        <span class="flex-1 break-words">${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('hiding');
        toast.addEventListener('animationend', () => {
            toast.remove();
        });
    }, 3000);
}

/* =============================================================================
   LOG VIEWER — Módulo completo del Visor de Logs (Modal Terminal)
============================================================================= */

function initLogViewer() {
    const backdrop = document.getElementById('log-modal-backdrop');
    const closeBtn = document.getElementById('log-modal-close-btn');

    if (!backdrop || !closeBtn) return;

    closeBtn.addEventListener('click', closeLogViewer);

    backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) closeLogViewer();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !backdrop.classList.contains('hidden')) {
            closeLogViewer();
        }
    });
}

async function openLogViewer(runId, dateStr = '') {
    const backdrop = document.getElementById('log-modal-backdrop');
    const title = document.getElementById('log-modal-title');
    const output = document.getElementById('log-output');

    if (!backdrop || !output) return;

    if (title) {
        title.textContent = `solba-backups — run ${runId}${dateStr ? '  ·  ' + dateStr : ''}`;
    }

    output.innerHTML = [
        '<div id="log-modal-loader">',
        '  <span class="terminal-cursor"></span>',
        `  <span class="text-slate-600 dark:text-slate-400">${t('status_loading_logs')}</span>`,
        '</div>'
    ].join('');

    backdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    try {
        const data = await api.getRunLogs(runId);
        const rawLogs = data.logs ?? data.output ?? data.content ?? '';
        renderLogs(output, rawLogs);

    } catch (error) {
        console.error('Error al cargar los logs:', error);
        output.innerHTML = [
            `<span class="log-line-error text-red-500">[ERROR] ${t('error_load_logs')}</span>\n`,
            `<span class="log-line-error text-red-500">${t('label_detail')}: ${escapeHtml(String(error.message))}</span>\n`,
            `<span class="log-line-default text-slate-600 dark:text-slate-400">${t('hint_check_endpoint')}</span>`
        ].join('');
    }
}

function closeLogViewer() {
    const backdrop = document.getElementById('log-modal-backdrop');
    if (backdrop) backdrop.classList.add('hidden');
    document.body.style.overflow = '';
}

function renderLogs(outputEl, rawLogs) {
    const lines = Array.isArray(rawLogs)
        ? rawLogs
        : String(rawLogs).split('\n');

    if (lines.length === 0 || (lines.length === 1 && lines[0].trim() === '')) {
        outputEl.innerHTML = `<span class="log-line-default text-slate-600 dark:text-slate-400">(${t('status_no_logs')})</span>`;
        return;
    }

    outputEl.innerHTML = lines.map(line => {
        const safe = escapeHtml(line);
        const upper = line.toUpperCase();

        if (upper.includes('[SUCCESS]') || upper.includes('SUCCESS')) return `<span class="text-green-500 font-medium">${safe}</span>`;
        if (upper.includes('[ERROR]') || upper.includes('ERROR')) return `<span class="text-red-500 font-medium">${safe}</span>`;
        if (upper.includes('[WARN]') || upper.includes('WARNING')) return `<span class="text-yellow-500 font-medium">${safe}</span>`;
        if (upper.includes('[INFO]') || upper.includes('[DEBUG]')) return `<span class="text-brand-500 font-medium">${safe}</span>`;
        return `<span class="text-slate-600 dark:text-slate-400">${safe}</span>`;
    }).join('\n');

    const body = document.getElementById('log-modal-body');
    if (body) body.scrollTop = body.scrollHeight;
}

function escapeHtml(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/* =============================================================================
   SETTINGS MODAL — Módulo de Ajustes Globales
============================================================================= */

function initSettingsModal() {
    const openBtn = document.getElementById('openSettingsBtn');
    const backdrop = document.getElementById('settings-backdrop');
    const closeBtn = document.getElementById('settings-close-btn');
    const cancelBtn = document.getElementById('settings-cancel-btn');
    const saveBtn = document.getElementById('settings-save-btn');

    if (!backdrop) return; 

    const tzSelect = document.getElementById('s-timezone');
    if (tzSelect) {
        tzSelect.innerHTML = `<option value="${SPAIN_TIMEZONE}">España (${SPAIN_TIMEZONE})</option>`;
        tzSelect.value = SPAIN_TIMEZONE;
        tzSelect.setAttribute('readonly', 'true');
        tzSelect.style.pointerEvents = 'none';
        tzSelect.classList.add('bg-slate-100', 'dark:bg-slate-800', 'opacity-80');
    }

    if (openBtn) openBtn.addEventListener('click', openSettingsModal);

    const closeModal = () => closeSettingsModal();
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) closeModal();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !backdrop.classList.contains('hidden')) closeModal();
    });

    document.querySelectorAll('.s-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchSettingsTab(btn.getAttribute('aria-controls')));
    });

    if (saveBtn) saveBtn.addEventListener('click', (e) => {
        e.preventDefault();
        handleSaveSettings(false);
    });

    const btnTestEmail = document.getElementById('btnTestEmail');
    if (btnTestEmail) {
        btnTestEmail.addEventListener('click', async (e) => {
            e.preventDefault();
            showToast(t('toast_sending_test_email'), 'success');
            btnTestEmail.disabled = true;
            const originalHtml = btnTestEmail.innerHTML;
            btnTestEmail.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${t('status_sending')}`;
            
            try {
                await handleSaveSettings(true);
                const response = await fetch('/api/v1/settings/test-email', { method: 'POST' });
                let result = null;
                try {
                    result = await response.json();
                } catch (_) {
                    result = null;
                }

                if (response.ok) {
                    const msg = (result && result.message) ? result.message : 'OK';
                    showToast(`${t('label_success')}: ` + msg, 'success');
                } else {
                    let detail = result ? (result.detail ?? result.message) : null;
                    if (detail && typeof detail === 'object') {
                        detail = detail.message ?? JSON.stringify(detail);
                    }
                    showToast(`${t('label_error')}: ` + (detail || t('error_email_unknown')), 'error');
                }
            } catch (err) {
                console.error(err);
                showToast(t('error_critical_server'), 'error');
            } finally {
                btnTestEmail.disabled = false;
                btnTestEmail.innerHTML = originalHtml;
            }
        });
    }
}

async function openSettingsModal() {
    const backdrop = document.getElementById('settings-backdrop');
    if (!backdrop) return;

    backdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    switchSettingsTab('tab-general');

    try {
        const settings = await api.getSettings();
        populateSettingsForm(settings);
    } catch (err) {
        console.warn('No se pudieron cargar los ajustes del servidor:', err.message);
    }
}

function closeSettingsModal() {
    const backdrop = document.getElementById('settings-backdrop');
    if (backdrop) backdrop.classList.add('hidden');
    document.body.style.overflow = '';
}

function switchSettingsTab(targetPanelId) {
    document.querySelectorAll('.s-tab-panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === targetPanelId);
    });
    document.querySelectorAll('.s-tab-btn').forEach(btn => {
        const isActive = btn.getAttribute('aria-controls') === targetPanelId;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-selected', String(isActive));
    });
}

function populateSettingsForm(s) {
    const set = (id, val) => {
        const el = document.getElementById(id);
        if (!el || val === undefined || val === null) return;
        if (el.type === 'checkbox') {
            if (val === 'true' || val === true || val === '1') el.checked = true;
            else if (val === 'false' || val === false || val === '0') el.checked = false;
            else el.checked = Boolean(val);
        }
        else el.value = val;
    };

    set('s-language', s.language || 'es');
    set('s-notify-email', s.notify_email);
    set('s-notify-errors-only', s.notify_errors_only);
    set('s-notify-whatsapp', s.notify_whatsapp);
    set('s-notification-email', s.notification_email);
    set('s-log-retention', s.log_retention_days);
    set('s-gdrive-credentials', s.gdrive_credentials_path);
    set('s-gdrive-folder', s.gdrive_folder_id);
    set('s-gdrive-scope', s.gdrive_scope);
    set('s-gdrive-auto-upload', s.gdrive_auto_upload);
    set('s-gdrive-delete-local', s.gdrive_delete_local);
    set('s-gdrive-max-files', s.gdrive_max_files);

    if (s.language) {
        applyTranslations(s.language);
    }
}

async function handleSaveSettings(silent = false) {
    const saveBtn = document.getElementById('settings-save-btn');
    if (!saveBtn) return;

    const get = (id) => {
        const el = document.getElementById(id);
        if (!el) return undefined;
        return el.type === 'checkbox' ? el.checked : el.value.trim();
    };

    const payload = {
        language: get('s-language') || 'es',
        notify_email: document.getElementById('s-notify-email') ? document.getElementById('s-notify-email').checked : undefined,
        notify_errors_only: document.getElementById('s-notify-errors-only') ? document.getElementById('s-notify-errors-only').checked : undefined,
        notify_whatsapp: document.getElementById('s-notify-whatsapp') ? document.getElementById('s-notify-whatsapp').checked : undefined,
        notification_email: get('s-notification-email') || undefined,
        timezone: get('s-timezone') || undefined,
        log_retention_days: Number(get('s-log-retention')) || undefined,
        gdrive_credentials_path: get('s-gdrive-credentials') || undefined,
        gdrive_folder_id: get('s-gdrive-folder') || undefined,
        gdrive_scope: get('s-gdrive-scope') || undefined,
        gdrive_auto_upload: get('s-gdrive-auto-upload'),
        gdrive_delete_local: get('s-gdrive-delete-local'),
        gdrive_max_files: Number(get('s-gdrive-max-files')) || undefined,
    };

    Object.keys(payload).forEach(k => payload[k] === undefined && delete payload[k]);

    saveBtn.disabled = true;
    saveBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${t('status_saving')}`;

    try {
        await api.saveSettings(payload);
        if (!silent) {
            showToast(`✅ ${t('toast_settings_saved')}`, 'success');
            applyTranslations(payload.language);
            closeSettingsModal();
            setTimeout(() => { location.reload(); }, 1500);
        }
    } catch (err) {
        console.error('Error al guardar los ajustes:', err);
        if (!silent) showToast(`❌ ${t('toast_settings_error')}`, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> ${t('btn_save_changes')}`;
    }
}

// ============================================================================
// AUTO-DESCUBRIMIENTO DE BASES DE DATOS
// ============================================================================

async function loadDiscovery() {
    const container = document.getElementById('discoveryContainer');
    if (!container) return;

    try {
        const response = await fetch('/api/v1/jobs/discovery');
        if (!response.ok) throw new Error(t('error_scan_network'));
        const services = await response.json();

        services.forEach(svc => {
            const currentLang = getCurrentLanguage();
            const translatedName = translateDiscoveryEngineName(svc, currentLang);
            const detectedAtText = t('discovery_detected_at', currentLang);
            const card = document.createElement('div');
            card.className = 'discovery-card cursor-pointer border border-slate-300 dark:border-slate-700 bg-white dark:bg-surface-950 hover:border-brand-500 dark:hover:border-brand-500 hover:bg-brand-50 rounded-lg p-4 transition-all shadow-sm min-h-[72px] flex items-center';
            card.dataset.engine = svc.engine;
            card.dataset.host = svc.host;
            card.dataset.port = svc.port;
            card.dataset.name = translatedName;

            card.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-full bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-500 dark:text-brand-400 pointer-events-none">
                        <i class="fa-solid fa-server"></i>
                    </div>
                    <div class="pointer-events-none">
                        <p class="text-sm font-semibold text-slate-800 dark:text-white">${translatedName}</p>
                        <p class="text-xs text-brand-500 dark:text-brand-400 font-mono">${detectedAtText} ${svc.host}:${svc.port}</p>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });

        document.querySelectorAll('.discovery-card').forEach(card => {
            card.addEventListener('click', handleDiscoveryClick);
        });

    } catch (error) {
        console.error('Error en autodescubrimiento:', error);
        document.querySelectorAll('.discovery-card').forEach(card => {
            card.addEventListener('click', handleDiscoveryClick);
        });
    }
}

function translateDiscoveryEngineName(service, lang = getCurrentLanguage()) {
    const engine = String(service?.engine || '').toLowerCase();
    const rawName = String(service?.name || '').trim();

    if (engine === 'postgresql') return t('engine_postgresql', lang);
    if (engine === 'mysql') return t('engine_mysql', lang);
    if (engine === 'sqlserver') return t('engine_sqlserver', lang);
    if (engine === 'sqlite') return t('engine_local_file', lang);
    if (engine === 'folder') return t('engine_local_folder', lang);

    const normalized = rawName.toLowerCase();
    if (normalized.includes('postgres')) return t('engine_postgresql', lang);
    if (normalized.includes('mysql') || normalized.includes('mariadb')) return t('engine_mysql', lang);
    if (normalized.includes('sql server') || normalized.includes('sqlserver')) return t('engine_sqlserver', lang);
    if (normalized.includes('sqlite') || normalized.includes('access')) return t('engine_local_file', lang);
    if (normalized.includes('carpeta') || normalized.includes('folder')) return t('engine_local_folder', lang);

    return rawName || t('engine_unknown', lang);
}

function handleDiscoveryClick(event) {
    const card = event.currentTarget;
    const engine = card.dataset.engine;
    const activeJobTypeCard = document.querySelector('.job-type-card.border-brand-500');
    const currentJobType = activeJobTypeCard ? activeJobTypeCard.dataset.jobType : 'db';

    document.querySelectorAll('.discovery-card').forEach(c => {
        c.classList.remove('border-brand-500', 'bg-brand-50', 'dark:bg-brand-500/10', 'ring-1', 'ring-brand-500');
    });
    card.classList.add('border-brand-500', 'bg-brand-50', 'dark:bg-brand-500/10', 'ring-1', 'ring-brand-500');

    const dbTypeEl = document.getElementById('dbType');
    const dbHostEl = document.getElementById('dbHost');
    const dbPortEl = document.getElementById('dbPort');
    const dbUserEl = document.getElementById('dbUser');
    const dbNameEl = document.getElementById('dbName');
    const dbFilePathContainer = document.getElementById('dbFilePathContainer');
    const dbCredentialsContainer = document.getElementById('dbCredentialsContainer');
    const networkDetails = document.querySelector('details.group');

    if (engine === 'sqlite' || engine === 'folder' || engine === 'mdb') {
        if (dbTypeEl) {
            dbTypeEl.value = engine;
            dbTypeEl.dispatchEvent(new Event('change'));
        }
        if (dbHostEl) dbHostEl.value = '';
        if (dbPortEl) dbPortEl.value = '';

        if (dbCredentialsContainer) {
            if (currentJobType === 'db') dbCredentialsContainer.classList.remove('hidden');
            else dbCredentialsContainer.classList.add('hidden');
        }
        if (networkDetails) networkDetails.classList.add('hidden');
        if (dbFilePathContainer) {
            if (currentJobType === 'db') dbFilePathContainer.classList.add('hidden');
            else dbFilePathContainer.classList.remove('hidden');
        }

        const dbFilePathEl = document.getElementById('dbFilePath');
        if (dbFilePathEl && currentJobType !== 'db') dbFilePathEl.focus();

    } else {
        if (dbTypeEl) {
            dbTypeEl.value = engine;
            dbTypeEl.dispatchEvent(new Event('change'));
        }
        if (dbHostEl) dbHostEl.value = card.dataset.host || '127.0.0.1';
        if (dbPortEl) dbPortEl.value = card.dataset.port || '';

        if (dbCredentialsContainer) dbCredentialsContainer.classList.remove('hidden');
        if (networkDetails) networkDetails.classList.remove('hidden');
        if (dbFilePathContainer) dbFilePathContainer.classList.add('hidden');

        if (dbUserEl) {
            const lang = getCurrentLanguage();
            if (engine === 'postgresql') dbUserEl.placeholder = t('ph_db_user', lang);
            else if (engine === 'sqlserver') dbUserEl.placeholder = t('ph_db_user_sqlserver', lang);
            else if (engine === 'mysql') dbUserEl.placeholder = t('ph_db_user_mysql', lang);
            else dbUserEl.placeholder = t('label_user', lang);
        }

        if (dbNameEl) dbNameEl.focus();
    }
}

// ============================================================================
// Lógica de Google Drive (OAuth2 + Google Picker API)
// ============================================================================

let gdriveAccessToken = null;
let gdriveClientId = null;
let pickerApiLoaded = false;

async function checkGoogleDriveStatus() {
    const authBox = document.getElementById('gdriveAuthBox');
    const pickerBox = document.getElementById('gdrivePickerBox');
    const emailSpan = document.getElementById('gdrive-connected-email');
    if (!authBox || !pickerBox) return;

    try {
        const res = await fetch('/api/v1/auth/google/status');
        const data = await res.json();

        if (data.authorized) {
            authBox.classList.add('hidden');
            pickerBox.classList.remove('hidden');
            if (emailSpan && data.email) {
                emailSpan.textContent = `(${data.email})`;
            }
        } else {
            authBox.classList.remove('hidden');
            pickerBox.classList.add('hidden');
            if (emailSpan) {
                emailSpan.textContent = '';
            }
        }
    } catch (e) {
        console.error("Error chequeando estado de Google Drive", e);
    }
}

document.getElementById('btnConnectDrive')?.addEventListener('click', () => {
    const w = 500;
    const h = 600;
    const left = (screen.width / 2) - (w / 2);
    const top = (screen.height / 2) - (h / 2);
    window.open('/api/v1/auth/google/login', 'GDrive Auth', `width=${w},height=${h},top=${top},left=${left}`);
});

window.addEventListener("message", (event) => {
    if (event.data === "GOOGLE_AUTH_SUCCESS") {
        checkGoogleDriveStatus();
    }
});

document.getElementById('btnDisconnectDrive')?.addEventListener('click', async () => {
    if (!(await showGenericConfirm('Google Drive', t('confirm_gdrive_disconnect'), t('btn_accept'), 'bg-red-600 hover:bg-red-700'))) return;

    try {
        const res = await fetch('/api/v1/auth/google/disconnect', { method: 'DELETE' });
        if (res.ok) {
            showToast(t('toast_gdrive_disconnected'), "success");
            checkGoogleDriveStatus();

            const destGDriveFolderId = document.getElementById('destGDriveFolderId');
            const destGDriveFolderName = document.getElementById('destGDriveFolderName');
            if (destGDriveFolderId) destGDriveFolderId.value = '';
            if (destGDriveFolderName) destGDriveFolderName.value = '';
        } else {
            showToast(t('toast_gdrive_disconnect_error'), "error");
        }
    } catch (e) {
        console.error("Error disconnecting", e);
        showToast(t('toast_connection_error'), "error");
    }
});

function loadGoogleApi() {
    gapi.load('picker', { 'callback': onPickerApiLoad });
}
function onPickerApiLoad() {
    pickerApiLoaded = true;
}

const gapiInterval = setInterval(() => {
    if (typeof gapi !== 'undefined') {
        clearInterval(gapiInterval);
        loadGoogleApi();
    }
}, 100);

document.getElementById('btnSelectDriveFolder')?.addEventListener('click', async () => {
    if (!pickerApiLoaded) {
        showToast(t('toast_picker_loading'), "error");
        return;
    }

    try {
        const res = await fetch('/api/v1/auth/google/token');
        if (!res.ok) throw new Error(t('error_get_token'));

        const data = await res.json();
        gdriveAccessToken = data.access_token;
        gdriveClientId = data.client_id;

        createPicker();
    } catch (e) {
        console.error(e);
        showToast(t('toast_picker_open_error'), "error");
    }
});

function createPicker() {
    if (!gdriveAccessToken) return;

    const view = new google.picker.DocsView(google.picker.ViewId.FOLDERS);
    view.setIncludeFolders(true);
    view.setSelectFolderEnabled(true);
    view.setMimeTypes('application/vnd.google-apps.folder');

    const picker = new google.picker.PickerBuilder()
        .enableFeature(google.picker.Feature.NAV_HIDDEN)
        .enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
        .setOAuthToken(gdriveAccessToken)
        .addView(view)
        .setTitle(t('picker_select_folder_title'))
        .setCallback(pickerCallback)
        .build();

    picker.setVisible(true);
}

function pickerCallback(data) {
    if (data.action === google.picker.Action.PICKED) {
        const doc = data.docs[0];
        const folderId = doc.id;
        const folderName = doc.name;

        document.getElementById('destGDriveFolderId').value = folderId;
        document.getElementById('destGDriveFolderName').value = folderName;

        showToast(`${t('toast_folder_selected')} "${folderName}"`, "success");
    }
}

async function loadTerminalLogs(runId) {
    const terminal = document.getElementById('bottomLogsTerminal');
    if (!terminal) return;

    terminal.innerHTML = `<span class="text-slate-500 italic">${t('status_loading_logs')} <i class="fa-solid fa-circle-notch fa-spin"></i></span>`;

    try {
        const res = await fetch(`/api/v1/history/run/${runId}/logs`);
        if (!res.ok) throw new Error(t('error_load_logs'));

        const data = await res.json();
        const logs = data.logs || t('status_no_logs_run');

        terminal.innerHTML = ''; 

        const lines = Array.isArray(logs) ? logs : String(logs).split('\n');
        lines.forEach(line => {
            const div = document.createElement('div');
            div.textContent = line;

            if (line.includes('[SUCCESS]')) div.className = 'text-green-500 font-medium';
            else if (line.includes('[ERROR]') || line.includes('[CRITICAL]')) div.className = 'text-red-500 font-medium';
            else if (line.includes('[WARNING]')) div.className = 'text-yellow-500';
            else if (line.includes('[INFO]')) div.className = 'text-brand-500';
            else div.className = 'text-slate-600 dark:text-slate-400';

            terminal.appendChild(div);
        });

        terminal.scrollTop = terminal.scrollHeight;

    } catch (e) {
        console.error("Error cargando logs:", e);
        terminal.innerHTML = `<span class="text-red-500 italic">${t('error_load_logs')}.</span>`;
    }
}

// ============================================================================
// SISTEMA DE TRADUCCIÓN (i18n)
// ============================================================================

const i18n = {
    es: {
        app_title: "SolbaBackups",
        title_create_job: "Crear Nueva Tarea",
        btn_new_job: "Nueva Tarea",
        sidebar_my_jobs: "Mis Tareas",
        btn_open_settings: "Ajustes Globales",
        stat_total_jobs: "Total de Tareas",
        stat_success_rate: "Tasa de Éxito",
        stat_storage_used: "Espacio Ocupado",
        label_job_name: "Nombre de la Tarea",
        label_job_type: "¿Qué vamos a respaldar?",
        job_type_db: "Copia de Base de Datos",
        job_type_folder: "Copia de Carpeta",
        job_type_sync: "Sincronización (Espejo)",
        section_db_credentials: "Acceso al Servidor",
        help_db_multiple: "Tip: Mantén pulsado Ctrl para seleccionar varias de la lista.",
        section_extra_options: "Opciones de Limpieza",
        help_retention_zero: "Pon 0 si quieres que NO se borre nada nunca.",
        btn_prev: "Anterior",
        btn_next: "Siguiente",
        prompt_new_local_folder: "Nueva carpeta local",
        ph_new_local_folder: "Nombre de la nueva carpeta",
        label_detected_engines: "Motores Detectados",
        title_new_backup_job: "Nueva Tarea de Backup",
        label_job_description: "Descripción",
        label_optional: "(opcional)",
        title_advanced_network: "Configuración Avanzada de Red",
        section_db_connection: "Conexión a la Base de Datos",
        label_db_engine: "Motor de Base de Datos",
        label_file_db: "Fichero (SQLite/Access)",
        label_db_host: "Host / IP del Servidor",
        label_port: "Puerto",
        title_schedule: "Programación",
        opt_schedule_manual: "Manual (solo bajo demanda)",
        opt_schedule_daily: "Diario (a una hora específica)",
        opt_schedule_weekly: "Semanal (día específico)",
        opt_schedule_monthly: "Mensual (día del mes)",
        opt_schedule_interval: "Por intervalo (minutos)",
        opt_schedule_cron: "Expresión Cron personalizada",
        opt_db_select_type: "Selecciona un tipo...",
        label_user: "Usuario",
        label_password: "Contraseña",
        label_db_name: "Nombre de la Base de Datos",
        label_schedule_time: "Hora de Ejecución",
        label_schedule_hour: "Hora",
        label_schedule_minute: "Minutos",
        label_day_of_week: "Día de la semana",
        label_day_of_month: "Día del mes",
        label_interval_minutes: "Intervalo en Minutos",
        label_cron_expression: "Expresión Cron",
        label_source_absolute_path: "Ruta absoluta del origen (Archivo o Carpeta)",
        day_monday: "Lunes",
        day_tuesday: "Martes",
        day_wednesday: "Miércoles",
        day_thursday: "Jueves",
        day_friday: "Viernes",
        day_saturday: "Sábado",
        day_sunday: "Domingo",
        label_storage: "Almacenamiento",
        section_backup_destination: "Destino del Backup",
        opt_local_folder: "Carpeta Local / Red",
        opt_google_drive: "Google Drive",
        engine_local_file: "Fichero Local",
        engine_local_folder: "Carpeta Local",
        engine_file_directory: "Directorio de archivos",
        engine_postgresql: "PostgreSQL",
        engine_mysql: "MySQL / MariaDB",
        engine_sqlserver: "Microsoft SQL Server",
        engine_unknown: "Motor detectado",
        discovery_detected_at: "Detectado en",
        label_dest_dir: "Directorio de Destino",
        gdrive_not_linked: "Google Drive no vinculado",
        gdrive_connect_hint: "Conecta tu cuenta para realizar backups automáticos en la nube.",
        btn_link_google: "Vincular con Google",
        gdrive_account_linked: "Cuenta Vinculada",
        gdrive_ready: "Lista para usar",
        btn_explore: "Explorar",
        label_gdrive_dest_folder: "Carpeta Destino Seleccionada",
        btn_save_job: "Guardar Configuración",
        title_execution_details: "Detalles de Ejecución",
        title_history_logs: "Historial y Logs",
        msg_select_execution: "Selecciona una ejecución en el historial para ver sus logs.",
        title_global_settings: "Ajustes Globales",
        tab_general: "General",
        section_application: "Aplicación",
        label_language: "Idioma",
        opt_lang_es: "Español",
        opt_lang_en: "English",
        label_admin_email: "Email del administrador",
        hint_admin_email: "Se usará para enviar alertas de errores críticos.",
        label_timezone: "Zona horaria del sistema",
        opt_detecting: "Detectando...",
        hint_timezone: "La zona horaria es detectada automáticamente por el sistema local.",
        section_notifications: "Notificaciones",
        label_notify_email: "Notificaciones por email",
        label_notification_email: "Correo de notificaciones",
        ph_notification_email: "tu@email.com",
        hint_notification_email: "Email donde se enviarán los reportes y alertas.",
        title_confirm: "Confirmar",
        hint_notify_email: "Recibe un resumen diario de las ejecuciones.",
        label_notify_whatsapp: "Notificaciones por WhatsApp",
        hint_notify_whatsapp: "Recibe alertas directamente en tu móvil.",
        label_notify_errors: "Alertas solo en caso de error",
        hint_notify_errors: "Solo notifica cuando un backup falla.",
        btn_test_email: "Enviar Notificación de Prueba",
        section_log_retention: "Retención de logs",
        label_log_retention: "Días de retención de historial",
        hint_log_retention: "Los registros más antiguos se eliminarán automáticamente.",
        btn_cancel: "Cancelar",
        btn_save_changes: "Guardar cambios",
        ph_job_name: "Ej: Copia nocturna de la base de datos",
        ph_job_title: "Ponle un nombre fácil, ej: Copias del lunes",
        ph_db_host: "Dirección del servidor (pregunta a tu informático)",
        ph_db_name: "Nombre exacto de tu base de datos",
        ph_db_user: "Ej: postgres",
        ph_db_user_sqlserver: "Ej: sa",
        ph_db_user_mysql: "Ej: root",
        ph_source_absolute_path: "Ruta completa al archivo o carpeta",
        ph_day_of_month: "Ej: 1",
        ph_schedule_interval: "Ej: 60",
        ph_cron_expression: "Ej: 0 2 * * *",
        ph_dest_dir: "¿Dónde quieres guardar las copias? Ej: D:\\Copias",
        help_job_name: "Un nombre corto para identificar esta copia de seguridad.",
        help_retention: "¿Cuántos días quieres conservar las copias? Pon 0 para guardarlas siempre.",
        help_db_engine: "Si no sabes cuál es, elige \"Fichero Local\" o pregunta a tu informático.",
        ph_gdrive_root: "Raíz de Mi Unidad",
        ph_admin_email: "admin@empresa.com",
        ph_log_retention_days: "30",
        empty_jobs_title: "No hay tareas",
        empty_jobs_desc: "No has configurado ningún backup aún.",
        empty_jobs_cta: "Nueva Tarea",
        empty_history: "No hay ejecuciones recientes.",
        error_loading_jobs: "Error cargando tareas.",
        error_loading_history: "Error cargando historial.",
        "Nuevo Job de Backup": "Nueva Tarea de Backup",
        "Nombre del Job": "Nombre de la Tarea",
        "Motores Detectados": "Motores Detectados",
        "Fichero Local": "Fichero Local",
        "Carpeta Local": "Carpeta Local",
        "Configuración Avanzada de Red": "Configuración Avanzada de Red",
        "Motor de Base de Datos": "Motor de Base de Datos",
        "Selecciona un tipo...": "Selecciona un tipo...",
        "Fichero (SQLite/Access)": "Fichero (SQLite/Access)",
        "Host / IP del Servidor": "Host / IP del Servidor",
        "Puerto": "Puerto",
        "Usuario": "Usuario",
        "Contraseña": "Contraseña",
        "Nombre de la Base de Datos": "Nombre de la Base de Datos",
        "Guardar Configuración": "Guardar Configuración",
        "Historial y Logs": "Historial y Logs",
        "Detalles de Ejecución": "Detalles de Ejecución",
        "Nombre": "Nombre",
        "Destino": "Destino",
        "Próxima Ej.": "Próxima Ej.",
        "Estado": "Estado",
        "Acciones": "Acciones",
        "Trabajos (Jobs)": "Tareas",
        "Directorio de Destino": "Directorio de Destino",
        "Almacenamiento": "Almacenamiento",
        "Carpeta Local / Red": "Carpeta Local / Red",
        "Google Drive": "Google Drive",
        "Programación": "Programación",
        "Diario (a una hora específica)": "Diario (a una hora específica)",
        "Manual (solo bajo demanda)": "Manual (solo bajo demanda)",
        "Aplicación": "Aplicación",
        "Idioma": "Idioma",
        "Email del administrador": "Email del administrador",
        "Notificaciones por email": "Notificaciones por email",
        "Alertas solo en caso de error": "Alertas solo en caso de error",
        "Retención de logs": "Retención de logs",
        "Días de retención": "Días de retención",
        "Ajustes Globales": "Ajustes Globales",
        "General": "General",
        "Enviar Notificación de Prueba": "Enviar Notificación de Prueba",
        "Guardar cambios": "Guardar cambios",
        "Editar": "Editar",
        "Borrar": "Borrar",
        "Ejecutar": "Ejecutar",
        "Cancelar": "Cancelar",
        "Google Drive no vinculado": "Google Drive no vinculado",
        "Zona horaria del sistema": "Zona horaria del sistema",
        "La zona horaria es detectada automáticamente por el sistema local.": "La zona horaria es detectada automáticamente por el sistema local.",
        "Notificaciones": "Notificaciones",
        "Recibe un resumen diario de las ejecuciones.": "Recibe un resumen diario de las ejecuciones.",
        "Solo notifica cuando un backup falla.": "Solo notifica cuando un backup falla.",
        "Días de retención de historial": "Días de retención de historial",
        "Los registros más antiguos se eliminarán automáticamente.": "Los registros más antiguos se eliminarán automáticamente.",
        "Se usará para enviar alertas de errores críticos.": "Se usará para enviar alertas de errores críticos.",
        "Vincular con Google": "Vincular con Google",
        "Desvincular Google Drive": "Desvincular Google Drive",
        "No hay tareas configuradas": "No hay tareas configuradas",
        "Crea un nuevo Job para empezar": "Crea una nueva Tarea para empezar",
        "Total de Tareas": "Total de Tareas",
        "Tasa de Éxito": "Tasa de Éxito",
        "Espacio Ocupado": "Espacio Ocupado",
        "Procesando...": "Procesando...",
        "Éxito": "Éxito",
        "Fallido": "Fallido",
        "N/A": "N/A",
        "Ej: Backup Base de Datos Producción": "Ej: Backup Base de Datos Producción",
        "Ej: Backup nocturno de la BD de producción": "Ej: Backup nocturno de la BD de producción",
        "Ej: 127.0.0.1 o mi-servidor.local": "Ej: 127.0.0.1 o mi-servidor.local",
        "Ej: mi_base_de_datos": "Ej: mi_base_de_datos",
        "Ej: postgres": "Ej: postgres",
        "Ej: C:\\MisBackups o \\\\Servidor\\Backups": "Ej: C:\\MisBackups o \\\\Servidor\\Backups",
        "Ej: C:\\Backups\\mi_base_datos.db o C:\\MisArchivos": "Ej: C:\\Backups\\mi_base_datos.db o C:\\MisArchivos",
        "Ej: 0 2 * * *": "Ej: 0 2 * * *",
        "Ej: 60": "Ej: 60",
        "/ruta/absoluta/credentials.json": "/ruta/absoluta/credentials.json",
        "Raíz de Mi Unidad": "Raíz de Mi Unidad",
        btn_restore: "Restaurar",
        btn_view_logs: "Ver Logs",
        confirm_restore: "¿Estás seguro de que quieres restaurar este backup? Esta acción sobrescribirá los datos actuales.",
        restore_success: "Backup restaurado correctamente.",
        restore_error: "Error al restaurar el backup. Revisa los logs para más detalles.",
        label_retention_days: "Días de retención",
        ph_retention_days: "Ej: 30",
        help_retention: "¿Cuántos días quieres conservar las copias? Pon 0 para guardarlas siempre.",
        engine_folder_sync: "Sincronización de Carpetas (Espejo)",
        title_smtp_server: "Servidor SMTP",
        label_smtp_host: "Host SMTP",
        label_smtp_port: "Puerto",
        label_smtp_user: "Usuario SMTP / Email",
        label_smtp_password: "Contraseña SMTP (App Password)",
        ph_smtp_host: "smtp.gmail.com",
        ph_smtp_port: "587",
        ph_smtp_user: "tu-correo@gmail.com",
        ph_smtp_password: "Contraseña de aplicación",
        btn_list_dbs: "Listar BDs",
        btn_test_connection: "Probar",
        btn_download: "Descargar",
        status_testing: "Probando...",
        status_checking: "Comprobando...",
        status_loading: "Cargando...",
        status_running: "Ejecutando...",
        status_saving: "Guardando...",
        status_sending: "Enviando...",
        status_scanning: "Escaneando...",
        status_waiting_path: "Esperando ruta...",
        status_loading_logs: "Cargando logs...",
        status_no_logs: "sin logs disponibles",
        status_no_logs_run: "No hay logs disponibles para esta ejecución.",
        stat_free_space_title: "Espacio Libre en Destino",
        badge_active: "Activo",
        badge_edit_mode: "modo edición",
        title_editing_job: "Editando Job",
        title_success: "¡Éxito!",
        title_restore_confirm: "Confirmar Restauración",
        title_file_explorer: "Explorador de Archivos",
        title_service_credentials: "Credenciales de servicio",
        title_upload_behavior: "Comportamiento de subida",
        label_sqlite_access: "SQLite / Access",
        label_job: "Tarea",
        label_free: "Libres",
        label_this_pc: "Este equipo",
        label_empty_folder: "Carpeta vacía",
        label_success: "ÉXITO",
        label_error: "ERROR",
        label_detail: "Detalle",
        label_credentials_path: "Ruta al archivo credentials.json",
        label_gdrive_folder_id: "ID de carpeta de destino",
        label_gdrive_scope: "Scope de acceso",
        label_auto_upload: "Subida automática tras backup",
        label_delete_local: "Borrar archivo local tras subida",
        label_max_files: "Máximo de archivos por carpeta en Drive",
        subtitle_file_explorer: "Selecciona una ruta para la configuración",
        btn_update_job: "Actualizar Tarea",
        btn_confirm_delete: "Sí, eliminar",
        btn_select_path: "Seleccionar Ruta",
        btn_accept: "Aceptar",
        btn_close_esc: "[ESC] Cerrar",
        title_run_logs: "solba-backups — run logs",
        msg_operation_success: "Operación realizada correctamente.",
        confirm_discard_new: "Tienes cambios sin guardar. ¿Estás seguro de que quieres descartarlos y crear una nueva Tarea?",
        confirm_discard_edit: "Tienes cambios sin guardar. ¿Estás seguro de que quieres descartarlos para editar esta Tarea?",
        confirm_delete_title: "¿Eliminar esta tarea?",
        confirm_delete_body: "se borrará de forma permanente.",
        confirm_gdrive_disconnect: "¿Seguro que quieres desvincular la cuenta de Google Drive?",
        error_field_required: "Este campo es obligatorio",
        error_select_engine: "Debes seleccionar un motor de BD",
        error_path_required: "Debes especificar la ruta absoluta del archivo/carpeta",
        error_load_logs: "No se pudieron cargar los logs",
        error_scan_network: "Error al escanear red",
        error_get_token: "No se pudo obtener el token",
        error_read_path: "Error al leer",
        error_email_unknown: "Fallo desconocido al enviar email",
        error_critical_server: "ERROR CRÍTICO: No se pudo contactar con el servidor. Revisa la consola.",
        hint_check_endpoint: "Verifica que el endpoint GET /api/v1/history/{runId}/logs esté disponible.",
        hint_gdrive_folder_id: "El ID aparece al final de la URL de la carpeta en Drive.",
        hint_auto_upload: "Sube el archivo comprimido a Drive al terminar.",
        hint_delete_local: "Libera espacio en disco después de la subida.",
        hint_max_files: "Los archivos más antiguos se eliminarán para no superar este límite.",
        toast_job_run_success: "Tarea ejecutada con éxito",
        toast_job_run_error: "Error al ejecutar la Tarea",
        toast_job_created: "¡Tarea creada con éxito!",
        toast_job_updated: "¡Tarea actualizada con éxito!",
        toast_job_save_error: "Error al guardar la Tarea. Revisa la consola.",
        toast_job_deleted: "Tarea eliminada correctamente",
        toast_job_delete_error: "No se pudo eliminar",
        toast_restore_no_id: "Error: No se pudo obtener el ID de la ejecución",
        toast_restore_server_error: "Error al restaurar en el servidor",
        toast_settings_saved: "Ajustes guardados correctamente",
        toast_settings_error: "Error al guardar los ajustes. Revisa la consola.",
        toast_sending_test_email: "Enviando correo de prueba, por favor espera...",
        toast_gdrive_disconnected: "Cuenta de Google Drive desvinculada",
        toast_gdrive_disconnect_error: "Error al desvincular la cuenta",
        toast_connection_error: "Error de conexión",
        toast_picker_loading: "La API de Google Picker aún se está cargando...",
        toast_picker_open_error: "Error al abrir el explorador de Drive. ¿Estás conectado?",
        toast_folder_selected: "Carpeta seleccionada",
        restore_in_progress: "Iniciando restauración...",
        picker_select_folder_title: "Selecciona la carpeta para los backups",
        // Nuevas claves
        btn_run_initial: "Ejecutar Backup Inicial",
        btn_sync_changes: "Sincronizar cambios",
        btn_delete: "Borrar",
        btn_yes_discard: "Sí, descartar",
        confirm_discard_title: "¿Descartar cambios?",
        toast_connection_ok: "✅ Conexión establecida correctamente",
        error_network: "Error de red o servidor",
        error_gdrive_quota: "Error al obtener cuota de Google Drive",
        error_create_folder: "Error al crear la carpeta en Drive",
        toast_drive_folder_created: "Carpeta creada y seleccionada:",
        ph_password_saved: "•••••••• (Contraseña guardada)",
        prompt_new_drive_folder: "Nombre de la nueva carpeta en Drive:",
        ph_new_drive_folder: "Mi carpeta de backups",
        status_creating: "Creando...",
        btn_create_folder: "Crear Carpeta",
        hint_gdrive_credentials: "Descárgalo desde Google Cloud Console."
    },
    en: {
        app_title: "SolbaBackups",
        title_create_job: "Create New Task",
        btn_new_job: "New Task",
        sidebar_my_jobs: "My Tasks",
        btn_open_settings: "Global Settings",
        stat_total_jobs: "Total Tasks",
        stat_success_rate: "Success Rate",
        stat_storage_used: "Used Space",
        label_job_name: "Task Name",
        label_job_type: "What are we backing up?",
        job_type_db: "Database Backup",
        job_type_folder: "Folder Backup",
        job_type_sync: "Sync (Mirror)",
        section_db_credentials: "Server Access",
        help_db_multiple: "Tip: Hold Ctrl to select multiple databases.",
        section_extra_options: "Cleanup Options",
        help_retention_zero: "Set 0 to never delete old backups.",
        btn_prev: "Previous",
        btn_next: "Next",
        prompt_new_local_folder: "New local folder",
        ph_new_local_folder: "New folder name",
        label_detected_engines: "Detected Engines",
        title_new_backup_job: "New Backup Task",
        label_job_description: "Description",
        label_optional: "(optional)",
        title_advanced_network: "Advanced Network Settings",
        section_db_connection: "Database Connection",
        label_db_engine: "Database Engine",
        label_file_db: "File (SQLite/Access)",
        label_db_host: "Server Host / IP",
        label_port: "Port",
        title_schedule: "Schedule",
        opt_schedule_manual: "Manual (on demand)",
        opt_schedule_daily: "Daily (specific time)",
        opt_schedule_weekly: "Weekly (specific day)",
        opt_schedule_monthly: "Monthly (day of month)",
        opt_schedule_interval: "By interval (minutes)",
        opt_schedule_cron: "Custom Cron expression",
        opt_db_select_type: "Select a type...",
        label_user: "User",
        label_password: "Password",
        label_db_name: "Database Name",
        label_schedule_time: "Execution Time",
        label_schedule_hour: "Hour",
        label_schedule_minute: "Minutes",
        label_day_of_week: "Day of week",
        label_day_of_month: "Day of month",
        label_interval_minutes: "Interval in Minutes",
        label_cron_expression: "Cron Expression",
        label_source_absolute_path: "Absolute source path (File or Folder)",
        day_monday: "Monday",
        day_tuesday: "Tuesday",
        day_wednesday: "Wednesday",
        day_thursday: "Thursday",
        day_friday: "Friday",
        day_saturday: "Saturday",
        day_sunday: "Sunday",
        label_storage: "Storage",
        section_backup_destination: "Backup Destination",
        opt_local_folder: "Local Folder / Network",
        opt_google_drive: "Google Drive",
        engine_local_file: "Local File",
        engine_local_folder: "Local Folder",
        engine_file_directory: "File directory",
        engine_postgresql: "PostgreSQL",
        engine_mysql: "MySQL / MariaDB",
        engine_sqlserver: "Microsoft SQL Server",
        engine_unknown: "Detected engine",
        discovery_detected_at: "Detected at",
        label_dest_dir: "Destination Directory",
        gdrive_not_linked: "Google Drive not linked",
        gdrive_connect_hint: "Connect your account to run automatic cloud backups.",
        btn_link_google: "Link with Google",
        gdrive_account_linked: "Linked Account",
        gdrive_ready: "Ready to use",
        btn_explore: "Browse",
        label_gdrive_dest_folder: "Selected Destination Folder",
        btn_save_job: "Save Configuration",
        title_execution_details: "Execution Details",
        title_history_logs: "History and Logs",
        msg_select_execution: "Select a history execution to view logs.",
        title_global_settings: "Global Settings",
        tab_general: "General",
        section_application: "Application",
        label_language: "Language",
        opt_lang_es: "Spanish",
        opt_lang_en: "English",
        label_admin_email: "Admin Email",
        hint_admin_email: "Used to send critical error alerts.",
        label_timezone: "System Timezone",
        opt_detecting: "Detecting...",
        hint_timezone: "Timezone is automatically detected from your local system.",
        section_notifications: "Notifications",
        label_notify_email: "Email Notifications",
        label_notification_email: "Notification Email",
        ph_notification_email: "you@email.com",
        hint_notification_email: "Email where reports and alerts will be sent.",
        title_confirm: "Confirm",
        hint_notify_email: "Receive a daily execution summary.",
        label_notify_whatsapp: "WhatsApp Notifications",
        hint_notify_whatsapp: "Receive alerts directly on your mobile.",
        label_notify_errors: "Alerts on errors only",
        hint_notify_errors: "Only notify when a backup fails.",
        btn_test_email: "Send Test Notification",
        section_log_retention: "Log Retention",
        label_log_retention: "History retention days",
        hint_log_retention: "Older records will be removed automatically.",
        btn_cancel: "Cancel",
        btn_save_changes: "Save changes",
        ph_job_name: "Ex: Nightly database backup",
        ph_job_title: "Give it a simple name, ex: Monday copies",
        ph_db_host: "Server address (ask your IT admin)",
        ph_db_name: "Exact name of your database",
        ph_db_user: "Ex: postgres",
        ph_db_user_sqlserver: "Ex: sa",
        ph_db_user_mysql: "Ex: root",
        ph_source_absolute_path: "Full path to the file or folder",
        ph_day_of_month: "Ex: 1",
        ph_schedule_interval: "Ex: 60",
        ph_cron_expression: "Ex: 0 2 * * *",
        ph_dest_dir: "Where do you want to save backups? Ex: D:\\Backups",
        help_job_name: "A short name to identify this backup task.",
        help_db_engine: "If unsure, choose \"Local File\" or ask your IT admin.",
        ph_gdrive_root: "Root of My Drive",
        ph_admin_email: "admin@company.com",
        ph_log_retention_days: "30",
        btn_restore: "Restore",
        btn_view_logs: "View Logs",
        confirm_restore: "Are you sure you want to restore this backup? This action will overwrite current data.",
        restore_success: "Backup restored successfully.",
        restore_error: "Error restoring backup. Check logs for details.",
        label_retention_days: "Retention Days",
        ph_retention_days: "Ex: 30",
        help_retention: "How many days do you want to keep backups? Set 0 to keep them forever.",
        engine_folder_sync: "Folder Sync (Mirror)",
        title_smtp_server: "SMTP Server",
        label_smtp_host: "SMTP Host",
        label_smtp_port: "Port",
        label_smtp_user: "SMTP User / Email",
        label_smtp_password: "SMTP Password (App Password)",
        ph_smtp_host: "smtp.gmail.com",
        ph_smtp_port: "587",
        ph_smtp_user: "your-email@gmail.com",
        ph_smtp_password: "App password",
        empty_jobs_title: "No tasks yet",
        empty_jobs_desc: "You have not configured any backup yet.",
        empty_jobs_cta: "New Job",
        empty_history: "No recent executions.",
        error_loading_jobs: "Error loading tasks.",
        error_loading_history: "Error loading history.",
        "Nuevo Job de Backup": "New Backup Task",
        "Nombre del Job": "Task Name",
        "Motores Detectados": "Discovered Engines",
        "Fichero Local": "Local File",
        "Carpeta Local": "Local Folder",
        "Configuración Avanzada de Red": "Advanced Network Settings",
        "Motor de Base de Datos": "Database Engine",
        "Selecciona un tipo...": "Select a type...",
        "Fichero (SQLite/Access)": "File (SQLite/Access)",
        "Host / IP del Servidor": "Server Host / IP",
        "Puerto": "Port",
        "Usuario": "User",
        "Contraseña": "Password",
        "Nombre de la Base de Datos": "Database Name",
        "Guardar Configuración": "Save Configuration",
        "Historial y Logs": "History and Logs",
        "Detalles de Ejecución": "Execution Details",
        "Nombre": "Name",
        "Destino": "Destination",
        "Próxima Ej.": "Next Run",
        "Estado": "Status",
        "Acciones": "Actions",
        "Trabajos (Jobs)": "Backup Tasks",
        "Directorio de Destino": "Destination Directory",
        "Almacenamiento": "Storage",
        "Carpeta Local / Red": "Local Folder / Network",
        "Google Drive": "Google Drive",
        "Programación": "Schedule",
        "Diario (a una hora específica)": "Daily (specific time)",
        "Manual (solo bajo demanda)": "Manual (on demand)",
        "Aplicación": "Application",
        "Idioma": "Language",
        "Email del administrador": "Admin Email",
        "Notificaciones por email": "Email Notifications",
        "Alertas solo en caso de error": "Alerts on error only",
        "Retención de logs": "Log Retention",
        "Días de retención": "Retention Days",
        "Ajustes Globales": "Global Settings",
        "General": "General",
        "Enviar Notificación de Prueba": "Send Test Notification",
        "Guardar cambios": "Save Changes",
        "Editar": "Edit",
        "Borrar": "Delete",
        "Ejecutar": "Run",
        "Cancelar": "Cancel",
        "Google Drive no vinculado": "Google Drive not linked",
        "Zona horaria del sistema": "System Timezone",
        "La zona horaria es detectada automáticamente por el sistema local.": "The timezone is automatically detected by the local system.",
        "Notificaciones": "Notifications",
        "Recibe un resumen diario de las ejecuciones.": "Receive a daily summary of executions.",
        "Solo notifica cuando un backup falla.": "Only notify when a backup fails.",
        "Días de retención de historial": "History retention days",
        "Los registros más antiguos se eliminarán automáticamente.": "Older records will be deleted automatically.",
        "Se usará para enviar alertas de errores críticos.": "Will be used to send critical error alerts.",
        "Vincular con Google": "Link with Google",
        "Desvincular Google Drive": "Unlink Google Drive",
        "No hay tareas configuradas": "No configured tasks",
        "Crea un nuevo Job para empezar": "Create a new Task to start",
        "Total de Tareas": "Total Tasks",
        "Tasa de Éxito": "Success Rate",
        "Espacio Ocupado": "Used Space",
        "Procesando...": "Processing...",
        "Éxito": "Success",
        "Fallido": "Failed",
        "N/A": "N/A",
        "Ej: Backup Base de Datos Producción": "Ex: Production Database Backup",
        "Ej: Backup nocturno de la BD de producción": "Ex: Nightly Production DB Backup",
        "Ej: 127.0.0.1 o mi-servidor.local": "Ex: 127.0.0.1 or my-server.local",
        "Ej: mi_base_de_datos": "Ex: my_database",
        "Ej: postgres": "Ex: postgres",
        "Ej: C:\\MisBackups o \\\\Servidor\\Backups": "Ex: C:\\MyBackups or \\\\Server\\Backups",
        "Ej: C:\\Backups\\mi_base_datos.db o C:\\MisArchivos": "Ex: C:\\Backups\\my_db.db or C:\\MyFiles",
        "Ej: 0 2 * * *": "Ex: 0 2 * * *",
        "Ej: 60": "Ex: 60",
        "/ruta/absoluta/credentials.json": "/absolute/path/to/credentials.json",
        "Raíz de Mi Unidad": "Root of My Drive",
        btn_list_dbs: "List Databases",
        btn_test_connection: "Test",
        btn_download: "Download",
        status_testing: "Testing...",
        status_checking: "Checking...",
        status_loading: "Loading...",
        status_running: "Running...",
        status_saving: "Saving...",
        status_sending: "Sending...",
        status_scanning: "Scanning...",
        status_waiting_path: "Waiting for path...",
        status_loading_logs: "Loading logs...",
        status_no_logs: "no logs available",
        status_no_logs_run: "No logs available for this execution.",
        stat_free_space_title: "Free Space at Destination",
        badge_active: "Active",
        badge_edit_mode: "edit mode",
        title_editing_job: "Editing Job",
        title_success: "Success!",
        title_restore_confirm: "Confirm Restore",
        title_file_explorer: "File Explorer",
        title_service_credentials: "Service Credentials",
        title_upload_behavior: "Upload Behavior",
        label_sqlite_access: "SQLite / Access",
        label_job: "Task",
        label_free: "Free",
        label_this_pc: "This PC",
        label_empty_folder: "Empty folder",
        label_success: "SUCCESS",
        label_error: "ERROR",
        label_detail: "Detail",
        label_credentials_path: "Path to credentials.json file",
        label_gdrive_folder_id: "Destination folder ID",
        label_gdrive_scope: "Access scope",
        label_auto_upload: "Auto-upload after backup",
        label_delete_local: "Delete local file after upload",
        label_max_files: "Maximum files per Drive folder",
        subtitle_file_explorer: "Select a path for configuration",
        btn_update_job: "Update Task",
        btn_confirm_delete: "Yes, delete",
        btn_select_path: "Select Path",
        btn_accept: "Accept",
        btn_close_esc: "[ESC] Close",
        title_run_logs: "solba-backups — run logs",
        msg_operation_success: "Operation completed successfully.",
        confirm_discard_new: "You have unsaved changes. Are you sure you want to discard them and create a new Task?",
        confirm_discard_edit: "You have unsaved changes. Are you sure you want to discard them to edit this Task?",
        confirm_delete_title: "Delete this task?",
        confirm_delete_body: "will be permanently deleted.",
        confirm_gdrive_disconnect: "Are you sure you want to unlink your Google Drive account?",
        error_field_required: "This field is required",
        error_select_engine: "Please select a database engine",
        error_path_required: "You must specify the absolute path of the file or folder",
        error_load_logs: "Failed to load logs",
        error_scan_network: "Error scanning network",
        error_get_token: "Could not obtain token",
        error_read_path: "Error reading path",
        error_email_unknown: "Unknown failure sending email",
        error_critical_server: "CRITICAL ERROR: Could not reach the server. Check the console.",
        hint_check_endpoint: "Verify that the endpoint GET /api/v1/history/{runId}/logs is available.",
        hint_gdrive_folder_id: "The ID appears at the end of the folder URL in Drive.",
        hint_auto_upload: "Uploads the compressed file to Drive upon completion.",
        hint_delete_local: "Frees up disk space after uploading.",
        hint_max_files: "Older files will be removed to stay within this limit.",
        toast_job_run_success: "Task executed successfully",
        toast_job_run_error: "Error running Task",
        toast_job_created: "Task created successfully!",
        toast_job_updated: "Task updated successfully!",
        toast_job_save_error: "Error saving the Task. Check the console.",
        toast_job_deleted: "Task deleted successfully",
        toast_job_delete_error: "Could not delete",
        toast_restore_no_id: "Error: Could not retrieve the execution ID",
        toast_restore_server_error: "Error restoring on the server",
        toast_settings_saved: "Settings saved successfully",
        toast_settings_error: "Error saving settings. Check the console.",
        toast_sending_test_email: "Sending test email, please wait...",
        toast_gdrive_disconnected: "Google Drive account unlinked",
        toast_gdrive_disconnect_error: "Error unlinking the account",
        toast_connection_error: "Connection error",
        toast_picker_loading: "Google Picker API is still loading...",
        toast_picker_open_error: "Error opening Drive explorer. Are you connected?",
        toast_folder_selected: "Folder selected",
        restore_in_progress: "Initiating restore...",
        picker_select_folder_title: "Select the folder for backups",
        // New keys
        btn_run_initial: "Run Initial Backup",
        btn_sync_changes: "Sync changes",
        btn_delete: "Delete",
        btn_yes_discard: "Yes, discard",
        confirm_discard_title: "Discard changes?",
        toast_connection_ok: "✅ Connection established successfully",
        error_network: "Network or server error",
        error_gdrive_quota: "Error fetching Google Drive quota",
        error_create_folder: "Error creating folder in Drive",
        toast_drive_folder_created: "Folder created and selected:",
        ph_password_saved: "•••••••• (Password saved)",
        prompt_new_drive_folder: "Name for the new Drive folder:",
        ph_new_drive_folder: "My backup folder",
        status_creating: "Creating...",
        btn_create_folder: "Create Folder",
        hint_gdrive_credentials: "Download it from Google Cloud Console."
    }

};

function getCurrentLanguage() {
    const langSelect = document.getElementById('s-language');
    if (langSelect && i18n[langSelect.value]) return langSelect.value;
    return 'es';
}

function t(key, lang = getCurrentLanguage()) {
    const language = i18n[lang] ? lang : 'es';
    const dict = i18n[language] || {};
    const fallback = i18n.es || {};
    const value = dict[key] ?? fallback[key];

    if (value === undefined) {
        console.warn(`[i18n] Missing translation key "${key}" for language "${language}".`);
        return key;
    }
    return value;
}

function applyTranslations(lang) {
    if (!i18n[lang]) {
        console.warn(`[i18n] Unknown language "${lang}", fallback to "es".`);
        lang = 'es';
    }
    const dict = i18n[lang] || {};
    const fallback = i18n.es || {};
    document.documentElement.lang = lang;

    document.querySelectorAll('[data-i18n]').forEach(el => {
        try {
            const key = el.getAttribute('data-i18n');
            if (!key) return;

            const translated = dict[key] ?? fallback[key];
            if (translated === undefined) {
                console.warn(`[i18n] Missing key "${key}" for language "${lang}".`);
                return;
            }

            if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
                el.placeholder = translated;
            } else {
                el.innerText = translated;
            }
        } catch (error) {
            console.warn('[i18n] Error translating element:', error);
        }
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        try {
            const key = el.getAttribute('data-i18n-placeholder');
            if (!key) return;

            const translated = dict[key] ?? fallback[key];
            if (translated === undefined) {
                console.warn(`[i18n] Missing placeholder key "${key}" for language "${lang}".`);
                return;
            }
            el.setAttribute('placeholder', translated);
        } catch (error) {
            console.warn('[i18n] Error translating placeholder:', error);
        }
    });
}

document.getElementById('s-language')?.addEventListener('change', (e) => {
    applyTranslations(e.target.value);
});

// ====== LÓGICA DEL ESCÁNER DE ESPACIO ======
let scanTimeout;
async function scanFreeSpace(path) {
    const statEl = document.getElementById('stat-free-space');
    const icon = document.getElementById('iconScanSpace');
    if (!statEl || !icon) return;

    const destTypeEl = document.getElementById('destType');
    const isGDrive = destTypeEl && destTypeEl.value === 'google_drive';

    if (!isGDrive && !path) {
        statEl.textContent = t('status_waiting_path');
        return;
    }

    icon.classList.add('fa-spin');
    statEl.textContent = t('status_scanning');

    try {
        let data;
        if (isGDrive) {
            const res = await fetch('/api/v1/utils/gdrive-space');
            if (!res.ok) throw new Error(t('error_gdrive_quota'));
            data = await res.json();
        } else {
            data = await api.getFreeSpace(path);
        }
        
        let space = data.free_space_mb;
        let unit = 'MB';
        if (space > 1024) {
            space = (space / 1024).toFixed(2);
            unit = 'GB';
        }
        statEl.textContent = `${space} ${unit} ${t('label_free')}`;
    } catch (error) {
        statEl.textContent = isGDrive ? t('gdrive_not_linked') : t('error_read_path');
        console.warn(`No se pudo escanear la ruta: ${error.message}`);
    } finally {
        icon.classList.remove('fa-spin');
    }
}

const destLocalInput = document.getElementById('destLocalPath');
if (destLocalInput) {
    destLocalInput.addEventListener('input', (e) => {
        clearTimeout(scanTimeout);
        scanTimeout = setTimeout(() => {
            scanFreeSpace(e.target.value.trim());
        }, 800);
    });
    if (destLocalInput.value.trim()) {
        scanFreeSpace(destLocalInput.value.trim());
    }
}

const destTypeInput = document.getElementById('destType');
if (destTypeInput) {
    destTypeInput.addEventListener('change', () => {
        if (destTypeInput.value === 'google_drive') {
            scanFreeSpace();
        } else if (destLocalInput) {
            scanFreeSpace(destLocalInput.value.trim());
        }
    });
    // Trigger on load for current value
    if (destTypeInput.value === 'google_drive') {
        scanFreeSpace();
    }
}

// ====== LÓGICA DEL EXPLORADOR DE ARCHIVOS WEB ======
let currentExplorerInput = null;
let currentExplorerPath = "";

async function openFileExplorer(inputId) {
    currentExplorerInput = document.getElementById(inputId);
    const modal = document.getElementById('fileExplorerModal');
    modal.classList.remove('hidden');
    await renderExplorerPath(""); 
}

function closeFileExplorer() {
    const modal = document.getElementById('fileExplorerModal');
    modal.classList.add('hidden');
    currentExplorerInput = null;
    currentExplorerPath = "";
}

async function renderExplorerPath(path) {
    currentExplorerPath = path;
    const container = document.getElementById('explorerListContainer');
    const pathDisplay = document.getElementById('explorerCurrentPath');
    const btnUp = document.getElementById('btnExplorerUp');

    container.innerHTML = '<div class="flex justify-center items-center h-40"><i class="fa-solid fa-spinner fa-spin text-brand-500 text-2xl"></i></div>';

    try {
        const data = await api.listDirectory(path);

        pathDisplay.textContent = data.current_path || t('label_this_pc');
        btnUp.disabled = !data.parent_path;
        btnUp.onclick = () => renderExplorerPath(data.parent_path);

        let html = '';
        if (data.folders.length === 0 && data.files.length === 0) {
            html = `<div class="text-center py-8 text-slate-500 text-sm">${t('label_empty_folder')}</div>`;
        } else {
            data.folders.forEach(f => {
                html += `
                    <div class="explorer-item flex items-center gap-3 p-2 hover:bg-slate-200 dark:hover:bg-surface-800 rounded cursor-pointer transition-colors" data-path="${f.path.replace(/\\/g, '\\\\')}">
                        <i class="fa-solid fa-folder text-brand-400 text-lg w-5 text-center"></i>
                        <span class="text-sm text-slate-700 dark:text-slate-300 select-none truncate">${f.name}</span>
                    </div>
                `;
            });
            data.files.forEach(f => {
                html += `
                    <div class="explorer-item flex items-center gap-3 p-2 hover:bg-slate-200 dark:hover:bg-surface-800 rounded cursor-pointer transition-colors" data-path="${f.path.replace(/\\/g, '\\\\')}">
                        <i class="fa-solid fa-file text-slate-400 text-lg w-5 text-center"></i>
                        <span class="text-sm text-slate-700 dark:text-slate-300 select-none truncate">${f.name}</span>
                    </div>
                `;
            });
        }
        container.innerHTML = html;

        container.querySelectorAll('.explorer-item').forEach(item => {
            item.addEventListener('click', () => {
                const targetPath = item.dataset.path;
                if (item.querySelector('.fa-folder')) {
                    renderExplorerPath(targetPath);
                } else {
                    currentExplorerPath = targetPath;
                    pathDisplay.textContent = targetPath;
                    container.querySelectorAll('.explorer-item').forEach(i => i.classList.remove('bg-brand-500/10', 'border', 'border-brand-500/50'));
                    item.classList.add('bg-brand-500/10', 'border', 'border-brand-500/50');
                }
            });
        });

    } catch (error) {
        container.innerHTML = `<div class="text-center py-8 text-red-500 text-sm"><i class="fa-solid fa-triangle-exclamation mb-2 text-xl"></i><br>Error: ${error.message}</div>`;
    }
}

document.getElementById('btnBrowseSource')?.addEventListener('click', () => openFileExplorer('dbFilePath'));
document.getElementById('btnBrowseDest')?.addEventListener('click', () => openFileExplorer('destLocalPath'));

document.getElementById('btnExplorerSelect')?.addEventListener('click', () => {
    if (currentExplorerInput && currentExplorerPath) {
        currentExplorerInput.value = currentExplorerPath;
        currentExplorerInput.dispatchEvent(new Event('input'));
    }
    closeFileExplorer();
});

document.getElementById('btnExplorerCancel')?.addEventListener('click', closeFileExplorer);
document.getElementById('btnCloseExplorer')?.addEventListener('click', closeFileExplorer);
document.getElementById('btnExplorerRefresh')?.addEventListener('click', () => renderExplorerPath(currentExplorerPath));

document.getElementById('btnExplorerCreateFolder')?.addEventListener('click', async () => {
    const parentPath = currentExplorerPath || '';
    const folderName = await showInputPrompt(
        t('prompt_new_local_folder') || 'Nueva carpeta',
        t('ph_new_local_folder') || 'Nombre de la carpeta'
    );
    if (!folderName || !folderName.trim()) return;

    const btn = document.getElementById('btnExplorerCreateFolder');
    const originalHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> ${t('status_creating') || 'Creando...'}`;
    }

    try {
        await api.createLocalDir(parentPath, folderName.trim());
        showToast(t('toast_folder_created') || `Carpeta "${folderName.trim()}" creada`, 'success');
        await renderExplorerPath(parentPath);
    } catch (error) {
        showToast(`${t('label_error') || 'Error'}: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }
});

document.getElementById('btnRestoreCancel')?.addEventListener('click', closeRestoreConfirmModal);
document.getElementById('btnRestoreConfirm')?.addEventListener('click', async () => {
    const runId = currentRestoreRunId;
    closeRestoreConfirmModal();
    if (runId) {
        await restoreBackup(runId);
    }
});
// Lógica para crear carpeta en Google Drive desde la UI
document.getElementById('btnCreateDriveFolder')?.addEventListener('click', async () => {
    const folderName = await showInputPrompt(t('prompt_new_drive_folder'), t('ph_new_drive_folder'));
    if (!folderName || !folderName.trim()) return;

    const btn = document.getElementById('btnCreateDriveFolder');
    const originalHtml = btn.innerHTML;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> ${t('status_creating')}`;
    btn.disabled = true;

    try {
        const res = await fetch('/api/v1/utils/gdrive-create-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_name: folderName.trim() })
        });
        
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || t('error_create_folder'));
        }
        
        const data = await res.json();
        
        const idInput = document.getElementById('destGDriveFolderId');
        const nameInput = document.getElementById('destGDriveFolderName');
        
        if (idInput) idInput.value = data.id;
        if (nameInput) nameInput.value = data.name;
        
        if (typeof showToast === 'function') {
            showToast(`${t('toast_drive_folder_created')} "${data.name}"`, "success");
        }
        
        if (idInput) idInput.dispatchEvent(new Event('change', { bubbles: true }));
        
    } catch (e) {
        console.error(e);
        showToast(`${t('label_error')}: ${e.message}`, "error");
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
});

function showGenericConfirm(title, message, confirmText, confirmClass = 'bg-brand-600 hover:bg-brand-700', iconClass = 'fa-solid fa-triangle-exclamation text-brand-400') {
    return new Promise((resolve) => {
        const container = document.getElementById('toast-container');
        if (!container) return resolve(false);

        const existing = document.getElementById('toast-generic-confirm');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.id = 'toast-generic-confirm';
        toast.className = 'toast';
        toast.style.cssText = [
            'background:#1e293b',
            'border:1px solid #334155',
            'min-width:320px',
            'flex-direction:column',
            'gap:0.75rem',
            'align-items:flex-start',
            'z-index: 9999999'
        ].join(';');
        toast.style.pointerEvents = 'auto';

        toast.innerHTML = `
            <div class="flex items-start gap-3">
                <i class="${iconClass} text-lg mt-0.5"></i>
                <div>
                    <p class="text-white text-sm font-semibold">${title}</p>
                    <p class="text-slate-400 text-xs mt-0.5 leading-relaxed">
                        ${message}
                    </p>
                </div>
            </div>
            <div class="flex gap-2 w-full mt-2">
                <button id="toast-confirm-ok"
                        class="flex-1 text-white text-xs font-semibold py-1.5 rounded-lg transition-colors ${confirmClass}">
                    ${confirmText}
                </button>
                <button id="toast-confirm-cancel"
                        class="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold py-1.5 rounded-lg transition-colors">
                    ${t('btn_cancel')}
                </button>
            </div>
        `;
        
        container.appendChild(toast);
        
        const btnOk = toast.querySelector('#toast-confirm-ok');
        const btnCancel = toast.querySelector('#toast-confirm-cancel');
        
        btnOk.addEventListener('click', () => {
            toast.classList.add('hiding');
            setTimeout(() => toast.remove(), 300);
            resolve(true);
        });
        
        btnCancel.addEventListener('click', () => {
            toast.classList.add('hiding');
            setTimeout(() => toast.remove(), 300);
            resolve(false);
        });
    });
}

function showInputPrompt(title, placeholder, confirmText = t('btn_accept') || 'Aceptar', confirmClass = 'bg-brand-600 hover:bg-brand-700', iconClass = 'fa-solid fa-pen text-brand-400') {
    return new Promise((resolve) => {
        const container = document.getElementById('toast-container');
        if (!container) return resolve(null);

        const existing = document.getElementById('toast-input-prompt');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.id = 'toast-input-prompt';
        toast.className = 'toast';
        toast.style.cssText = [
            'background:#1e293b',
            'border:1px solid #334155',
            'min-width:320px',
            'flex-direction:column',
            'gap:0.75rem',
            'align-items:flex-start',
            'z-index: 9999999'
        ].join(';');
        toast.style.pointerEvents = 'auto';

        toast.innerHTML = `
            <div class="flex items-start gap-3 w-full">
                <i class="${iconClass} text-lg mt-0.5"></i>
                <div class="w-full pr-2">
                    <p class="text-white text-sm font-semibold">${title}</p>
                    <input type="text" id="toast-prompt-input" class="w-full bg-slate-900 border border-slate-600 text-white text-sm rounded p-2 mt-2 outline-none focus:border-brand-500" placeholder="${placeholder || ''}">
                </div>
            </div>
            <div class="flex gap-2 w-full mt-2">
                <button id="toast-confirm-ok"
                        class="flex-1 text-white text-xs font-semibold py-1.5 rounded-lg transition-colors ${confirmClass}">
                    ${confirmText}
                </button>
                <button id="toast-confirm-cancel"
                        class="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold py-1.5 rounded-lg transition-colors">
                    ${t('btn_cancel') || 'Cancelar'}
                </button>
            </div>
        `;
        
        container.appendChild(toast);
        
        const inputField = toast.querySelector('#toast-prompt-input');
        const btnOk = toast.querySelector('#toast-confirm-ok');
        const btnCancel = toast.querySelector('#toast-confirm-cancel');
        
        setTimeout(() => inputField.focus(), 50);

        const handleResolve = (val) => {
            toast.classList.add('hiding');
            setTimeout(() => toast.remove(), 300);
            resolve(val);
        };

        btnOk.addEventListener('click', () => {
            handleResolve(inputField.value);
        });
        
        btnCancel.addEventListener('click', () => {
            handleResolve(null);
        });

        inputField.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') handleResolve(inputField.value);
            if (e.key === 'Escape') handleResolve(null);
        });
    });
}

// --- WIZARD LOGIC ---
let currentWizardStep = 1;

function showWizardStep(step) {
    const s1 = document.getElementById('wizardStep1');
    const s2 = document.getElementById('wizardStep2');
    const s3 = document.getElementById('wizardStep3');
    const form = document.getElementById('createJobForm');
    
    const btnPrev = document.getElementById('btnWizardPrev');
    const btnNext = document.getElementById('btnWizardNext');
    const btnSave = document.getElementById('btnSaveJob');

    clearAllErrors(form || document);

    // Hide all
    if (s1) s1.classList.add('hidden');
    if (s2) s2.classList.add('hidden');
    if (s3) s3.classList.add('hidden');

    if (step === 1) {
        if (s1) s1.classList.remove('hidden');
        if (btnPrev) btnPrev.classList.add('hidden');
        if (btnNext) btnNext.classList.remove('hidden');
        if (btnSave) btnSave.classList.add('hidden');
    } else if (step === 2) {
        if (s2) s2.classList.remove('hidden');
        if (btnPrev) btnPrev.classList.remove('hidden');
        if (btnNext) btnNext.classList.remove('hidden');
        if (btnSave) btnSave.classList.add('hidden');
    } else if (step === 3) {
        if (s3) s3.classList.remove('hidden');
        if (btnPrev) btnPrev.classList.remove('hidden');
        if (btnNext) btnNext.classList.add('hidden');
        if (btnSave) {
            btnSave.classList.remove('hidden');
            resetSaveButtonState(btnSave);
        }
    }

    currentWizardStep = step;
}

document.addEventListener('DOMContentLoaded', () => {
    // Wait slightly to ensure elements exist
    setTimeout(() => {
        const btnPrev = document.getElementById('btnWizardPrev');
        const btnNext = document.getElementById('btnWizardNext');
        const btnCancelEditTop = document.getElementById('btnCancelEditTop');

        if (btnPrev) {
            btnPrev.addEventListener('click', () => {
                if (currentWizardStep > 1) showWizardStep(currentWizardStep - 1);
            });
        }

        if (btnNext) {
            btnNext.addEventListener('click', () => {
                const form = document.getElementById('createJobForm');
                clearAllErrors(form || document);
                const jobName = document.getElementById('jobName');
                if (currentWizardStep === 1) {
                    if (!jobName || !jobName.value.trim()) {
                        if (jobName) showError(jobName, t('error_field_required') || 'Obligatorio');
                        return;
                    }
                    clearErrors(jobName);
                    showWizardStep(2);
                } else if (currentWizardStep === 2) {
                    const activeJobTypeCard = document.querySelector('.job-type-card.border-brand-500');
                    const currentJobType = activeJobTypeCard ? activeJobTypeCard.dataset.jobType : 'db';
                    const dbType = document.getElementById('dbType');
                    const dbHost = document.getElementById('dbHost');
                    const dbPort = document.getElementById('dbPort');
                    const dbUser = document.getElementById('dbUser');
                    const dbPassword = document.getElementById('dbPassword');
                    const dbName = document.getElementById('dbName');
                    const dbFilePath = document.getElementById('dbFilePath');

                    let step2Valid = true;

                    if (currentJobType === 'db') {
                        if (!dbType || !dbType.value.trim()) {
                            if (dbType) showError(dbType, t('error_select_engine') || 'Obligatorio');
                            step2Valid = false;
                        } else if (dbType) {
                            clearErrors(dbType);
                        }
                        const isFileEngine = dbType && (dbType.value === 'sqlite' || dbType.value === 'mdb');
                        if (!isFileEngine) {
                            if (!dbHost || !dbHost.value.trim()) {
                                if (dbHost) showError(dbHost, t('error_field_required') || 'Host obligatorio');
                                step2Valid = false;
                            } else if (dbHost) {
                                clearErrors(dbHost);
                            }

                            if (!dbPort || !dbPort.value.trim()) {
                                if (dbPort) showError(dbPort, t('error_field_required') || 'Puerto obligatorio');
                                step2Valid = false;
                            } else if (dbPort) {
                                clearErrors(dbPort);
                            }

                            if (!dbUser || !dbUser.value.trim()) {
                                if (dbUser) showError(dbUser, t('error_field_required') || 'Usuario obligatorio');
                                step2Valid = false;
                            } else if (dbUser) {
                                clearErrors(dbUser);
                            }

                            if (!isPasswordUnchangedInEditMode()) {
                                if (!dbPassword || !dbPassword.value.trim()) {
                                    if (dbPassword) showError(dbPassword, t('error_field_required') || 'Contraseña obligatoria');
                                    step2Valid = false;
                                } else if (dbPassword) {
                                    clearErrors(dbPassword);
                                }
                            } else if (dbPassword) {
                                clearErrors(dbPassword);
                            }

                        }

                        const selectedDbs = dbName && dbName.tagName.toLowerCase() === 'select'
                            ? Array.from(dbName.selectedOptions).map(opt => opt.value).filter(Boolean)
                            : [];
                        if (!dbName || selectedDbs.length === 0) {
                            if (dbName) showError(dbName, t('error_field_required') || 'Selecciona al menos una BD');
                            step2Valid = false;
                        } else if (dbName) {
                            clearErrors(dbName);
                        }
                    } else {
                        if (!dbFilePath || !dbFilePath.value.trim()) {
                            if (dbFilePath) showError(dbFilePath, t('error_path_required') || 'Especifica la ruta de origen');
                            step2Valid = false;
                        } else if (dbFilePath) {
                            clearErrors(dbFilePath);
                        }
                    }

                    if (!step2Valid) {
                        btnNext.classList.add('animate-shake');
                        setTimeout(() => btnNext.classList.remove('animate-shake'), 400);
                        return;
                    }
                    showWizardStep(3);
                }
            });
        }

        if (btnCancelEditTop) {
            btnCancelEditTop.addEventListener('click', () => {
                isFormDirty = false;
                resetFormToCreateMode();
            });
        }

        showWizardStep(1);
    }, 100);
});
// --- END WIZARD LOGIC ---