/**
 * app.js - Lógica principal de la UI para SolbaBackups
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Obtener Jobs y pintar pantalla central
    loadJobs();

    // 2. Obtener Historial y pintar panel derecho
    loadHistory();

    // 3. Inicializar validación del formulario
    initJobFormValidation();

    // 4. Iniciar polling (Radar) silencioso
    setupPolling();

    // 5. Inicializar el Visor de Logs (modal terminal)
    initLogViewer();

    // 6. Inicializar el modal de Ajustes Globales
    initSettingsModal();
});

/**
 * Carga la lista de Jobs desde la API y los renderiza en la pantalla central.
 * Incluye botones de Ejecutar, Editar y Borrar en cada tarjeta.
 */
async function loadJobs(isSilent = false) {
    const container = document.getElementById('jobs-container');
    if (!container) return;

    try {
        const jobs = await api.getJobs();
        container.innerHTML = '';

        if (jobs.length === 0) {
            container.innerHTML = '<p class="text-slate-400">No hay jobs configurados.</p>';
            return;
        }

        jobs.forEach(job => {
            const jobId = job._id || job.id || job.job_id;

            const jobCard = document.createElement('div');
            jobCard.className = 'bg-surface-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 group';
            jobCard.dataset.jobId = jobId;

            jobCard.innerHTML = `
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-3 mb-1">
                        <div class="w-8 h-8 rounded-lg bg-brand-500/10 text-brand-400 flex items-center justify-center shrink-0">
                            <i class="fa-solid fa-server"></i>
                        </div>
                        <h3 class="text-lg font-semibold text-white truncate">${job.name || 'Job sin nombre'}</h3>
                    </div>
                    <p class="text-sm text-slate-400 mt-2">
                        ${job.description || 'Sin descripción'} &bull; Schedule: <span class="text-slate-300">${job.schedule || 'Manual'}</span>
                    </p>
                </div>

                <!-- Grupo de acciones -->
                <div class="flex items-center gap-2 shrink-0">
                    <!-- Ejecutar -->
                    <button class="btn-ejecutar bg-brand-500 hover:bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm flex items-center gap-1.5"
                            data-id="${jobId}" title="Ejecutar ahora">
                        <i class="fa-solid fa-play"></i>
                        <span>Ejecutar</span>
                    </button>

                    <!-- Editar -->
                    <button class="btn-edit-job w-9 h-9 flex items-center justify-center rounded-lg border border-slate-700 bg-surface-800 text-amber-400 hover:bg-amber-400/10 hover:border-amber-400/50 transition-colors"
                            data-id="${jobId}"
                            data-name="${job.name || ''}"
                            data-description="${job.description || ''}"
                            data-schedule="${job.schedule_type || 'manual'}"
                            data-db-type="${job.db_type || ''}"
                            data-db-host="${job.db_host || ''}"
                            data-db-port="${job.db_port || ''}"
                            data-db-name="${job.db_name || ''}"
                            data-db-user="${job.db_user || ''}"
                            title="Editar Job">
                        <i class="fa-solid fa-pen text-xs"></i>
                    </button>

                    <!-- Borrar -->
                    <button class="btn-delete-job w-9 h-9 flex items-center justify-center rounded-lg border border-slate-700 bg-surface-800 text-red-400 hover:bg-red-400/10 hover:border-red-400/50 transition-colors"
                            data-id="${jobId}"
                            data-name="${job.name || 'este job'}"
                            title="Eliminar Job">
                        <i class="fa-solid fa-trash-can text-xs"></i>
                    </button>
                </div>
            `;

            // Asignar listeners directamente al elemento (evita problemas con re-renders)
            jobCard.querySelector('.btn-ejecutar').addEventListener('click', handleRunJob);
            jobCard.querySelector('.btn-edit-job').addEventListener('click', handleEditJob);
            jobCard.querySelector('.btn-delete-job').addEventListener('click', handleDeleteJob);

            container.appendChild(jobCard);
        });

    } catch (error) {
        if (!isSilent) {
            console.error('Error cargando los jobs:', error);
            container.innerHTML = '<p class="text-red-400">Error al cargar los jobs. Revisa la consola.</p>';
        }
    }
}

/**
 * Maneja el clic en el botón de Ejecutar.
 */
async function handleRunJob(event) {
    const button = event.currentTarget;
    const jobId = button.dataset.id;
    const icon = button.querySelector('i');
    const textSpan = button.querySelector('span');

    // Deshabilitar botón y mostrar 'Ejecutando...'
    button.disabled = true;
    button.classList.add('opacity-70', 'cursor-not-allowed');
    icon.className = 'fa-solid fa-spinner fa-spin mr-1.5';
    textSpan.textContent = 'Ejecutando...';

    try {
        // Llama al endpoint de ejecución manual
        await api.runJob(jobId);

        // Alerta de éxito
        showToast(`¡Job ${jobId} ejecutado con éxito!`, 'success');

        // Refrescar el historial para ver la nueva ejecución
        loadHistory();

    } catch (error) {
        console.error(`Error al ejecutar el job ${jobId}:`, error);
        showToast(`Hubo un error al ejecutar el Job ${jobId}.`, 'error');
    } finally {
        // Restaurar estado del botón
        button.disabled = false;
        button.classList.remove('opacity-70', 'cursor-not-allowed');
        icon.className = 'fa-solid fa-play mr-1.5';
        textSpan.textContent = 'Ejecutar';
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

        // Limpiamos contenido estático
        container.innerHTML = '';

        if (historyData.length === 0) {
            container.innerHTML = '<p class="text-slate-400 text-sm">No hay ejecuciones recientes.</p>';
            return;
        }

        // Pintamos cada registro del historial
        historyData.forEach(record => {
            const isSuccess = record.status === 'SUCCESS';

            // Clases dinámicas dependiendo del estado
            const statusClass = isSuccess
                ? 'bg-green-500/10 text-green-400 border-green-500/20'
                : 'bg-red-500/10 text-red-400 border-red-500/20';

            const borderClass = isSuccess
                ? 'border-slate-700 hover:border-brand-500'
                : 'border-red-500/30 hover:border-red-500';

            // Formatear la fecha
            const dateObj = new Date(record.timestamp || record.end_time || Date.now());
            const dateStr = dateObj.toLocaleString();

            // El ID del run puede ser _id, id, run_id o el que devuelva el backend
            const runId = record._id || record.id || record.run_id || null;

            const historyItem = document.createElement('div');
            historyItem.className = `bg-surface-800 border rounded-lg p-3 cursor-pointer transition-colors ${borderClass}`;
            if (runId) historyItem.dataset.runId = runId;

            historyItem.innerHTML = `
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-semibold text-slate-300">${dateStr}</span>
                    <div class="flex items-center gap-2">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold ${statusClass} border uppercase tracking-wide">
                            ${record.status}
                        </span>
                        ${runId ? `
                        <button class="btn-view-logs w-6 h-6 flex items-center justify-center rounded text-slate-500 hover:text-green-400 hover:bg-green-500/10 transition-colors" 
                                data-run-id="${runId}" 
                                title="Ver logs de esta ejecución">
                            <i class="fa-solid fa-terminal text-[10px]"></i>
                        </button>` : ''}
                    </div>
                </div>
                <div class="flex items-center gap-4 text-xs text-slate-400">
                    <div class="flex items-center gap-1.5">
                        <i class="fa-solid fa-server"></i> Job ID: ${record.job_id || 'N/A'}
                    </div>
                </div>
                ${!isSuccess && record.error_message ? `<p class="text-[11px] text-red-400 truncate mt-2">Error: ${record.error_message}</p>` : ''}
            `;

            // Clic en el ítem completo -> abrir logs
            historyItem.addEventListener('click', (e) => {
                // Evitar doble disparo si se hizo clic en el botón interno
                if (e.target.closest('.btn-view-logs')) return;
                if (runId) openLogViewer(runId, dateStr);
            });

            // Clic en el botón de terminal también abre el modal
            const logBtn = historyItem.querySelector('.btn-view-logs');
            if (logBtn) {
                logBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openLogViewer(runId, dateStr);
                });
            }

            container.appendChild(historyItem);
        });

    } catch (error) {
        if (!isSilent) {
            console.error('Error cargando historial:', error);
            container.innerHTML = '<p class="text-red-400 text-sm">Error cargando historial.</p>';
        }
    }
}

/**
 * Inicializa la validación del formulario.
 * Soporta modo CREACIÓN (POST) y modo EDICIÓN (PUT).
 */
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

    if (!form || !btnSave) return;

    // ── Mostrar/ocultar campos condicionales al cambiar la frecuencia ──
    if (scheduleType) {
        scheduleType.addEventListener('change', () => updateScheduleFields(scheduleType.value));
        // Estado inicial (por defecto "manual" — no muestra nada extra)
        updateScheduleFields(scheduleType.value);
    }
    // Botón «Cancelar edición» (se inyecta dinámicamente en setFormEditMode)
    form.addEventListener('click', (e) => {
        if (e.target.closest('#btnCancelEdit')) resetFormToCreateMode();
    });

    btnSave.addEventListener('click', async (e) => {
        e.preventDefault();
        let isValid = true;

        clearErrors(jobName);
        clearErrors(dbType);

        if (jobName.value.trim() === '') {
            showError(jobName, 'Este campo es obligatorio');
            isValid = false;
        }
        if (dbType.value.trim() === '') {
            showError(dbType, 'Debes seleccionar un motor de BD');
            isValid = false;
        }

        if (!isValid) {
            btnSave.classList.add('animate-shake');
            setTimeout(() => btnSave.classList.remove('animate-shake'), 400);
            return;
        }

        const editingId = form.dataset.editingId || null;

        // ── Recoger campos de schedule ──────────────────────────────────
        const scheduleVal = scheduleType ? scheduleType.value : 'manual';
        const intervalMinutes = scheduleIntervalEl && scheduleVal === 'interval'
            ? (parseInt(scheduleIntervalEl.value) || null)
            : null;
        const cronExpr = scheduleCronEl && scheduleVal === 'cron'
            ? (scheduleCronEl.value.trim() || null)
            : null;

        // ── Payload PLANO según esquema del backend ────────────────────────
        const jobData = {
            name: jobName.value.trim(),
            description: jobDesc ? jobDesc.value.trim() || null : null,
            db_type: dbType.value || 'postgresql',
            db_host: dbHost ? dbHost.value.trim() || null : null,
            db_port: dbPort ? parseInt(dbPort.value) || null : null,
            db_name: dbName ? dbName.value.trim() || null : null,
            db_user: dbUser ? dbUser.value.trim() || null : null,
            db_password: dbPassword && dbPassword.value ? dbPassword.value : undefined,
            schedule: jobSched ? jobSched.value : 'manual',
        };
        // Limpiar claves con undefined (no enviar la clave si está vacía)
        Object.keys(jobData).forEach(k => jobData[k] === undefined && delete jobData[k]);

        btnSave.disabled = true;
        btnSave.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';

        try {
            if (editingId) {
                // ── MODO EDICIÓN: PUT ──────────────────────────────────────
                await api.updateJob(editingId, jobData);
                showToast(`¡Job «${jobData.name}» actualizado con éxito!`, 'success');
                resetFormToCreateMode();
            } else {
                // ── MODO CREACIÓN: POST ────────────────────────────────────
                await api.createJob(jobData);
                showToast('¡Job creado con éxito!', 'success');
                form.reset();
            }
            loadJobs();
        } catch (error) {
            showToast('Error al guardar el Job. Revisa la consola.', 'error');
        } finally {
            btnSave.disabled = false;
            btnSave.innerHTML = editingId
                ? '<i class="fa-solid fa-floppy-disk"></i> Actualizar Job'
                : '<i class="fa-solid fa-floppy-disk"></i> Guardar Configuración';
        }
    });
}

/**
 * Rellena el formulario con los datos del job y activa el modo edición.
 * @param {Event} event
 */
function handleEditJob(event) {
    const btn = event.currentTarget;
    const id = btn.dataset.id;
    const name = btn.dataset.name;
    const sch = btn.dataset.schedule;
    // Leer todos los campos extra del dataset
    const extra = {
        db_type: btn.dataset.dbType || '',
        db_host: btn.dataset.dbHost || '',
        db_port: btn.dataset.dbPort || '',
        db_name: btn.dataset.dbName || '',
        db_user: btn.dataset.dbUser || '',
        description: btn.dataset.description || '',
        schedule_type: btn.dataset.schedule || 'manual',
    };

    setFormEditMode(id, name, extra, sch);

    // Scroll suave hasta el formulario
    const form = document.getElementById('createJobForm');
    if (form) form.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Muestra el modal de confirmación para borrar un job.
 * @param {Event} event
 */
function handleDeleteJob(event) {
    const btn = event.currentTarget;
    const jobId = btn.dataset.id;
    const name = btn.dataset.name || `Job ${jobId}`;
    showDeleteConfirm(jobId, name);
}

/**
 * Activa el formulario en modo edición: cambia el título, el botón
 * y guarda el ID del job que se está editando.
 */
function setFormEditMode(id, name, extra = {}, schedule) {
    const form = document.getElementById('createJobForm');
    const jobName = document.getElementById('jobName');
    const dbType = document.getElementById('dbType');
    const dbHost = document.getElementById('dbHost');
    const dbPort = document.getElementById('dbPort');
    const dbName = document.getElementById('dbName');
    const dbUser = document.getElementById('dbUser');
    const scheduleType = document.getElementById('scheduleType');
    const scheduleIntervalEl = document.getElementById('scheduleIntervalMinutes');
    const scheduleCronEl = document.getElementById('scheduleCron');
    const btnSave = document.getElementById('btnSaveJob');
    const heading = form ? form.querySelector('h3') : null;

    if (!form) return;

    // Guardar ID
    form.dataset.editingId = id;

    // Rellenar campos básicos de BD
    if (jobName) jobName.value = name;
    if (dbType) dbType.value = extra.db_type || '';
    if (jobDesc) jobDesc.value = extra.description || '';
    if (jobSched) jobSched.value = extra.schedule_type || 'manual';
    if (dbHost) dbHost.value = extra.db_host || '';
    if (dbPort) dbPort.value = extra.db_port || '';
    if (dbName) dbName.value = extra.db_name || '';
    if (dbUser) dbUser.value = extra.db_user || '';
    // La contraseña NO se precarga por seguridad

    // Rellenar y mostrar/ocultar los campos de schedule
    const schedVal = schedule || 'manual';
    if (scheduleType) scheduleType.value = schedVal;
    if (scheduleIntervalEl) scheduleIntervalEl.value = extra.schedule_interval_minutes || '';
    if (scheduleCronEl) scheduleCronEl.value = extra.schedule_cron || '';
    updateScheduleFields(schedVal);

    // Cambiar título con badge
    if (heading) {
        heading.innerHTML = `
            Editando Job
            <span id="edit-mode-badge"
                  class="ml-2 px-2 py-0.5 rounded text-xs font-semibold bg-amber-400/10 text-amber-400 border border-amber-400/30">
                modo edición
            </span>`;
    }

    // Cambiar botón guardar
    if (btnSave) {
        btnSave.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Actualizar Job';
        btnSave.classList.replace('bg-brand-500', 'bg-amber-500');
        btnSave.classList.replace('hover:bg-brand-600', 'hover:bg-amber-600');
    }

    // Añadir botón «Cancelar» si no existe ya
    if (!form.querySelector('#btnCancelEdit')) {
        const cancelBtn = document.createElement('button');
        cancelBtn.id = 'btnCancelEdit';
        cancelBtn.type = 'button';
        cancelBtn.className = 'ml-2 px-4 py-2.5 rounded-lg text-sm font-medium border border-slate-600 text-slate-300 hover:bg-surface-800 transition-colors';
        cancelBtn.innerHTML = '<i class="fa-solid fa-xmark mr-1.5"></i>Cancelar';
        btnSave.parentElement.appendChild(cancelBtn);
    }
}

/**
 * Resetea el formulario a modo creación (limpia todo el estado de edición).
 */
function resetFormToCreateMode() {
    const form = document.getElementById('createJobForm');
    const btnSave = document.getElementById('btnSaveJob');
    const heading = form ? form.querySelector('h3') : null;

    if (!form) return;

    form.reset();
    delete form.dataset.editingId;
    delete form.dataset.editingSchedule;

    // Restaurar título
    if (heading) heading.innerHTML = 'Nuevo Job de Backup';

    // Restaurar botón guardar
    if (btnSave) {
        btnSave.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Guardar Configuración';
        btnSave.classList.replace('bg-amber-500', 'bg-brand-500');
        btnSave.classList.replace('hover:bg-amber-600', 'hover:bg-brand-600');
    }

    // Eliminar botón cancelar
    const cancelBtn = form.querySelector('#btnCancelEdit');
    if (cancelBtn) cancelBtn.remove();
    const badge = form.querySelector('#edit-mode-badge');
    if (badge) badge.remove();

    // Ocultar campos condicionales del schedule
    updateScheduleFields('manual');
}

/**
 * Muestra u oculta los campos condicionales de Schedule según el tipo elegido.
 * @param {string} value - Valor del select scheduleType
 */
function updateScheduleFields(value) {
    const intervalWrap = document.getElementById('scheduleIntervalWrap');
    const cronWrap = document.getElementById('scheduleCronWrap');
    if (intervalWrap) intervalWrap.classList.toggle('hidden', value !== 'interval');
    if (cronWrap) cronWrap.classList.toggle('hidden', value !== 'cron');
}

/**
 * Muestra un Toast de confirmación de borrado en lugar del confirm() bloqueante.
 * Incluye dos botones: Confirmar y Cancelar.
 * @param {string|number} jobId - ID del job a borrar
 * @param {string}        name  - Nombre legible del job
 */
function showDeleteConfirm(jobId, name) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    // Evitar duplicados si se pulsa muy rápido
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

    toast.innerHTML = `
        <div class="flex items-start gap-3">
            <i class="fa-solid fa-triangle-exclamation text-red-400 text-lg mt-0.5"></i>
            <div>
                <p class="text-white text-sm font-semibold">¿Eliminar este job?</p>
                <p class="text-slate-400 text-xs mt-0.5 leading-relaxed">
                    «${name}» se borrará de forma permanente.
                </p>
            </div>
        </div>
        <div class="flex gap-2 w-full">
            <button id="toast-delete-ok"
                    class="flex-1 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold py-1.5 rounded-lg transition-colors">
                <i class="fa-solid fa-trash-can mr-1"></i> Sí, eliminar
            </button>
            <button id="toast-delete-cancel"
                    class="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold py-1.5 rounded-lg transition-colors">
                Cancelar
            </button>
        </div>
    `;

    container.appendChild(toast);

    const removeToast = () => {
        toast.classList.add('hiding');
        toast.addEventListener('animationend', () => toast.remove(), { once: true });
    };

    // Confirmar → DELETE
    toast.querySelector('#toast-delete-ok').addEventListener('click', async () => {
        removeToast();
        try {
            await api.deleteJob(jobId);
            showToast(`Job «${name}» eliminado correctamente.`, 'success');
            loadJobs();
        } catch (err) {
            console.error('Error al eliminar el job:', err);
            showToast(`No se pudo eliminar «${name}». Revisa la consola.`, 'error');
        }
    });

    // Cancelar → solo cierra
    toast.querySelector('#toast-delete-cancel').addEventListener('click', removeToast);

    // Auto-cierre tras 8 segundos si el usuario no hace nada
    setTimeout(removeToast, 8000);
}

/**
 * Pinta de rojo el input y añade el texto de error debajo
 */
function showError(inputElement, message) {
    inputElement.classList.add('input-error');

    // Crear el elemento del mensaje de error
    const errorText = document.createElement('div');
    errorText.className = 'error-message';
    // Le añadimos un pequeño icono de alerta
    errorText.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> ${message}`;

    // Lo insertamos justo después del input (al final del div contenedor)
    inputElement.parentElement.appendChild(errorText);
}

/**
 * Limpia el estado de error de un input
 */
function clearErrors(inputElement) {
    inputElement.classList.remove('input-error');

    // Buscar si ya existe un mensaje de error y borrarlo
    const existingError = inputElement.parentElement.querySelector('.error-message');
    if (existingError) {
        existingError.remove();
    }
}

/**
 * Tarea 1: El Radar (Polling Automático)
 * Configura un polling silencioso cada 8 segundos.
 */
function setupPolling() {
    setInterval(async () => {
        try {
            // isSilent = true para no sobreescribir la UI con errores si cae el servidor
            await Promise.all([
                loadJobs(true),
                loadHistory(true)
            ]);
        } catch (error) {
            console.warn('Polling error (silenciado):', error);
        }
    }, 8000);
}

/**
 * Tarea 2: Sistema de Notificaciones Flotantes (Toasts)
 * Muestra una notificación flotante.
 * @param {string} message - El mensaje a mostrar.
 * @param {string} type - Tipo de toast: 'success' o 'error'.
 */
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icon = type === 'success'
        ? '<i class="fa-solid fa-circle-check text-lg"></i>'
        : '<i class="fa-solid fa-circle-exclamation text-lg"></i>';

    toast.innerHTML = `
        ${icon}
        <span>${message}</span>
    `;

    container.appendChild(toast);

    // Auto-desaparecer tras 3 segundos
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

/**
 * Inicializa los listeners del modal de logs (cerrar con botón, Escape y backdrop).
 * Llamar una sola vez al cargar el DOM.
 */
function initLogViewer() {
    const backdrop = document.getElementById('log-modal-backdrop');
    const closeBtn = document.getElementById('log-modal-close-btn');

    if (!backdrop || !closeBtn) return;

    // Botón [ESC] Cerrar
    closeBtn.addEventListener('click', closeLogViewer);

    // Clic en el fondo oscuro cierra el modal
    backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) closeLogViewer();
    });

    // Tecla Escape cierra el modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !backdrop.classList.contains('hidden')) {
            closeLogViewer();
        }
    });
}

/**
 * Abre el modal de logs, actualiza el título y dispara la carga de datos.
 * @param {string|number} runId   - ID de la ejecución
 * @param {string}        dateStr - Fecha formateada para mostrar en el título
 */
async function openLogViewer(runId, dateStr = '') {
    const backdrop = document.getElementById('log-modal-backdrop');
    const title = document.getElementById('log-modal-title');
    const output = document.getElementById('log-output');

    if (!backdrop || !output) return;

    // Actualizar título con el run_id y fecha
    if (title) {
        title.textContent = `solba-backups — run ${runId}${dateStr ? '  ·  ' + dateStr : ''}`;
    }

    // Mostrar estado de carga dentro del terminal
    output.innerHTML = [
        '<div id="log-modal-loader">',
        '  <span class="terminal-cursor"></span>',
        '  <span>Cargando logs...</span>',
        '</div>'
    ].join('');

    // Mostrar el backdrop
    backdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden'; // Evitar scroll del fondo

    try {
        const data = await api.getRunLogs(runId);

        // El backend puede devolver { logs: "texto" } o { logs: ["linea1", ...] }
        const rawLogs = data.logs ?? data.output ?? data.content ?? '';
        renderLogs(output, rawLogs);

    } catch (error) {
        console.error('Error al cargar los logs:', error);
        output.innerHTML = [
            '<span class="log-line-error">[ERROR] No se pudieron cargar los logs.</span>\n',
            `<span class="log-line-error">Detalle: ${escapeHtml(String(error.message))}</span>\n`,
            '<span class="log-line-default">Verifica que el endpoint GET /api/v1/history/{runId}/logs esté disponible.</span>'
        ].join('');
    }
}

/**
 * Cierra el modal de logs y restaura el estado.
 */
function closeLogViewer() {
    const backdrop = document.getElementById('log-modal-backdrop');
    if (backdrop) backdrop.classList.add('hidden');
    document.body.style.overflow = '';
}

/**
 * Convierte el texto de logs (string o array) en HTML coloreado y lo inyecta
 * en el elemento <pre> del modal.
 * @param {HTMLElement} outputEl - El elemento <pre id="log-output">
 * @param {string|Array} rawLogs - El texto crudo de logs
 */
function renderLogs(outputEl, rawLogs) {
    // Normalizar a array de líneas
    const lines = Array.isArray(rawLogs)
        ? rawLogs
        : String(rawLogs).split('\n');

    if (lines.length === 0 || (lines.length === 1 && lines[0].trim() === '')) {
        outputEl.innerHTML = '<span class="log-line-default">(sin logs disponibles)</span>';
        return;
    }

    // Colorizar cada línea según el nivel
    outputEl.innerHTML = lines.map(line => {
        const safe = escapeHtml(line);
        const upper = line.toUpperCase();

        if (upper.includes('[SUCCESS]') || upper.includes('SUCCESS')) return `<span class="log-line-success">${safe}</span>`;
        if (upper.includes('[ERROR]') || upper.includes('ERROR')) return `<span class="log-line-error">${safe}</span>`;
        if (upper.includes('[WARN]') || upper.includes('WARNING')) return `<span class="log-line-warn">${safe}</span>`;
        if (upper.includes('[INFO]') || upper.includes('[DEBUG]')) return `<span class="log-line-info">${safe}</span>`;
        return `<span class="log-line-default">${safe}</span>`;
    }).join('\n');

    // Hacer scroll hasta el final (como una terminal real)
    const body = document.getElementById('log-modal-body');
    if (body) body.scrollTop = body.scrollHeight;
}

/**
 * Escapa caracteres HTML especiales para prevenir XSS al inyectar texto de logs.
 * @param {string} str
 * @returns {string}
 */
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

/**
 * Inicializa el modal de Ajustes: conecta todos los listeners de UI.
 * Llama una única vez al cargar el DOM.
 */
function initSettingsModal() {
    const openBtn = document.getElementById('openSettingsBtn');
    const backdrop = document.getElementById('settings-backdrop');
    const closeBtn = document.getElementById('settings-close-btn');
    const cancelBtn = document.getElementById('settings-cancel-btn');
    const saveBtn = document.getElementById('settings-save-btn');

    if (!backdrop) return; // El modal no está en el DOM — salir silenciosamente

    // ── Abrir modal ───────────────────────────────────────────
    if (openBtn) openBtn.addEventListener('click', openSettingsModal);

    // ── Cerrar modal ─────────────────────────────────────────
    const closeModal = () => closeSettingsModal();
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    // Clic en el fondo oscuro cierra el modal
    backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) closeModal();
    });

    // Tecla Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !backdrop.classList.contains('hidden')) closeModal();
    });

    // ── Sistema de pestañas ──────────────────────────────────
    document.querySelectorAll('.s-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchSettingsTab(btn.getAttribute('aria-controls')));
    });

    // ── Guardar ajustes ────────────────────────────────────
    if (saveBtn) saveBtn.addEventListener('click', handleSaveSettings);
}

/**
 * Abre el modal de ajustes y carga los datos actuales desde el backend.
 */
async function openSettingsModal() {
    const backdrop = document.getElementById('settings-backdrop');
    if (!backdrop) return;

    backdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Resetear a la primera pestaña
    switchSettingsTab('tab-general');

    // Intentar cargar configuración actual del backend
    try {
        const settings = await api.getSettings();
        populateSettingsForm(settings);
    } catch (err) {
        // Si la API aún no existe o falla, el formulario queda en blanco
        console.warn('No se pudieron cargar los ajustes del servidor:', err.message);
    }
}

/**
 * Cierra el modal de ajustes.
 */
function closeSettingsModal() {
    const backdrop = document.getElementById('settings-backdrop');
    if (backdrop) backdrop.classList.add('hidden');
    document.body.style.overflow = '';
}

/**
 * Activa la pestaña indicada y desactiva las demás.
 * @param {string} targetPanelId - ID del panel a mostrar ('tab-general' | 'tab-gdrive')
 */
function switchSettingsTab(targetPanelId) {
    // Paneles
    document.querySelectorAll('.s-tab-panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === targetPanelId);
    });
    // Botones de pestaña
    document.querySelectorAll('.s-tab-btn').forEach(btn => {
        const isActive = btn.getAttribute('aria-controls') === targetPanelId;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-selected', String(isActive));
    });
}

/**
 * Rellena todos los campos del formulario con los datos recibidos del backend.
 * Solo asigna el campo si la clave existe en el objeto para respetar defaults.
 * @param {Object} s - Objeto de configuración tal como lo devuelve el backend
 */
function populateSettingsForm(s) {
    const set = (id, val) => {
        const el = document.getElementById(id);
        if (!el || val === undefined || val === null) return;
        if (el.type === 'checkbox') el.checked = Boolean(val);
        else el.value = val;
    };

    // ── General ───────────────────────────────────────────
    set('s-app-name', s.app_name);
    set('s-admin-email', s.admin_email);
    set('s-timezone', s.timezone);
    set('s-notify-email', s.notify_email);
    set('s-notify-errors-only', s.notify_errors_only);
    set('s-log-retention', s.log_retention_days);

    // ── Google Drive ─────────────────────────────────────
    set('s-gdrive-credentials', s.gdrive_credentials_path);
    set('s-gdrive-folder', s.gdrive_folder_id);
    set('s-gdrive-scope', s.gdrive_scope);
    set('s-gdrive-auto-upload', s.gdrive_auto_upload);
    set('s-gdrive-delete-local', s.gdrive_delete_local);
    set('s-gdrive-max-files', s.gdrive_max_files);
}

/**
 * Recoge todos los valores del formulario y los envía al backend.
 * El payload sigue el esquema de claves que espera el servidor.
 */
async function handleSaveSettings() {
    const saveBtn = document.getElementById('settings-save-btn');
    if (!saveBtn) return;

    const get = (id) => {
        const el = document.getElementById(id);
        if (!el) return undefined;
        return el.type === 'checkbox' ? el.checked : el.value.trim();
    };

    // Construir payload tipado
    const payload = {
        // General
        app_name: get('s-app-name') || undefined,
        admin_email: get('s-admin-email') || undefined,
        timezone: get('s-timezone') || undefined,
        notify_email: get('s-notify-email'),
        notify_errors_only: get('s-notify-errors-only'),
        log_retention_days: Number(get('s-log-retention')) || undefined,

        // Google Drive
        gdrive_credentials_path: get('s-gdrive-credentials') || undefined,
        gdrive_folder_id: get('s-gdrive-folder') || undefined,
        gdrive_scope: get('s-gdrive-scope') || undefined,
        gdrive_auto_upload: get('s-gdrive-auto-upload'),
        gdrive_delete_local: get('s-gdrive-delete-local'),
        gdrive_max_files: Number(get('s-gdrive-max-files')) || undefined,
    };

    // Eliminar claves undefined para no enviar campos vacíos innecesarios
    Object.keys(payload).forEach(k => payload[k] === undefined && delete payload[k]);

    // Estado de carga
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';

    try {
        await api.saveSettings(payload);
        showToast('¡Ajustes guardados correctamente!', 'success');
        closeSettingsModal();
    } catch (err) {
        console.error('Error al guardar los ajustes:', err);
        showToast('Error al guardar los ajustes. Revisa la consola.', 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Guardar cambios';
    }
}
