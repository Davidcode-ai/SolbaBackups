/**
 * app.js - Lógica principal de la UI para SolbaBackups
 */

let isFormDirty = false; // Estado para saber si hay cambios sin guardar

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
        const result = await api.getSettings();
        if (result && result.settings && result.settings.language) {
            applyTranslations(result.settings.language);
            const langSelect = document.getElementById('s-language');
            if (langSelect) langSelect.value = result.settings.language;
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
                    <p class="text-sm font-medium text-slate-800 dark:text-slate-200 mb-1">No hay tareas</p>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mb-4">No has configurado ningún backup aún.</p>
                    <button onclick="document.getElementById('jobName').focus();" class="bg-brand-500 hover:bg-brand-600 text-white px-4 py-2 rounded-lg text-xs font-medium transition-all shadow-sm">
                        Nueva Tarea
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
            if(job.db_type === 'folder') iconClass = "fa-solid fa-folder-tree";
            else if(job.db_type === 'sqlite' || job.db_type === 'mdb') iconClass = "fa-solid fa-file-lines";

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
                    data-dest-gdrive-folder-name="${job.dest_gdrive_folder_name || ''}">
                    <i class="${iconClass} w-4 text-center group-hover:text-brand-400 transition-colors"></i>
                    <div class="flex-1 truncate">
                        <p class="text-sm font-medium group-hover:text-brand-400 transition-colors">${job.name || 'Job sin nombre'}</p>
                        <p class="text-[10px] text-slate-500 truncate">${job.db_type} • ${job.schedule_type || 'manual'}</p>
                    </div>
                </div>
                
                <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    <button class="btn-ejecutar w-6 h-6 flex items-center justify-center rounded bg-brand-500/10 text-brand-400 hover:bg-brand-500 hover:text-white transition-colors" data-id="${jobId}" title="Ejecutar">
                        <i class="fa-solid fa-play text-[10px]"></i>
                    </button>
                    <button class="btn-delete-job w-6 h-6 flex items-center justify-center rounded bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white transition-colors" data-id="${jobId}" title="Borrar">
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
            container.innerHTML = '<p class="px-3 text-xs text-red-400">Error cargando jobs.</p>';
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
    // Como era un botón cuadrado pequeño (w-6 h-6), le cambiamos las clases para que quepa el texto
    button.className = 'btn-ejecutar flex items-center gap-1.5 px-2 py-1 rounded bg-brand-500/10 text-brand-500 opacity-70 cursor-not-allowed transition-all';
    button.innerHTML = `
        <svg class="animate-spin h-3 w-3 text-brand-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span class="text-[10px] font-semibold">Ejecutando...</span>
    `;

    try {
        // Llama al endpoint de ejecución manual
        await api.runJob(jobId);
        showToast(`¡Job ${jobId} ejecutado con éxito!`, 'success');
        loadHistory();
    } catch (error) {
        console.error(`Error al ejecutar el job ${jobId}:`, error);
        showToast(`Hubo un error al ejecutar el Job ${jobId}.`, 'error');
    } finally {
        // 3. Restaurar estado original del botón sea cual sea el resultado
        button.disabled = false;
        button.className = originalClass;
        button.innerHTML = originalHtml;
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
            const isSuccess = (record.status || '').toUpperCase() === 'SUCCESS';

            // Clases dinámicas dependiendo del estado
            const statusClass = isSuccess
                ? 'bg-green-500/10 text-green-400 border-green-500/20'
                : 'bg-red-500/10 text-red-400 border-red-500/20';

            const borderClass = isSuccess
                ? 'border-slate-300 dark:border-slate-700 hover:border-brand-500'
                : 'border-red-500/30 hover:border-red-500';

            // Formatear la fecha
            const dateObj = new Date(record.timestamp || record.end_time || Date.now());
            const dateStr = dateObj.toLocaleString();

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
                <div class="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
                    <div class="flex items-center gap-1.5">
                        <i class="fa-solid fa-server"></i> Job ID: ${record.job_id || 'N/A'}
                    </div>
                </div>
                ${!isSuccess && record.error_message ? `<p class="text-[11px] text-red-400 truncate mt-2">Error: ${record.error_message}</p>` : ''}
            `;
            
            // Clic en el ítem completo -> cargar terminal
            historyItem.addEventListener('click', (e) => {
                if (e.target.closest('.btn-view-logs')) return;
                loadTerminalLogs(runId);
            });
            
            // Si el html sigue teniendo el botón interno de vista, lo asociamos a un modal grande
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
    
    // Destinos
    const destType = document.getElementById('destType');
    const destLocalPath = document.getElementById('destLocalPath');
    const destGDriveFolderId = document.getElementById('destGDriveFolderId');
    const destLocalPathContainer = document.getElementById('destLocalPathContainer');
    const destGDriveContainer = document.getElementById('destGDriveContainer');
    const dbFilePathContainer = document.getElementById('dbFilePathContainer');
    const dbCredentialsContainer = document.getElementById('dbCredentialsContainer');
    const networkDetails = document.querySelector('details.group');
    const dbFilePath = document.getElementById('dbFilePath');
    
    // Marcar el formulario como "dirty" cuando algo cambie
    form.addEventListener('input', () => { isFormDirty = true; });
    form.addEventListener('change', () => { isFormDirty = true; });

    // Botón "Nuevo Job" de la sidebar
    const btnNewJobSidebar = document.getElementById('btnNewJobSidebar');
    if (btnNewJobSidebar) {
        btnNewJobSidebar.addEventListener('click', () => {
            if (isFormDirty) {
                const confirmDiscard = confirm("Tienes cambios sin guardar. ¿Estás seguro de que quieres descartarlos y crear un nuevo Job?");
                if (!confirmDiscard) return;
            }
            
            // Limpiar formulario y estado
            resetFormToCreateMode();
        });
    }
    // Elementos de programación
    const scheduleIntervalContainer = document.getElementById('scheduleIntervalContainer');
    const scheduleCronContainer = document.getElementById('scheduleCronContainer');
    const scheduleTimeContainer = document.getElementById('scheduleTimeContainer');
    const scheduleDayOfWeekContainer = document.getElementById('scheduleDayOfWeekContainer');
    const scheduleDayOfMonthContainer = document.getElementById('scheduleDayOfMonthContainer');
    const jobScheduleInterval = document.getElementById('jobScheduleInterval');
    const jobScheduleCron = document.getElementById('jobScheduleCron');
    const jobScheduleTime = document.getElementById('jobScheduleTime');
    const jobScheduleDayOfWeek = document.getElementById('jobScheduleDayOfWeek');
    const jobScheduleDayOfMonth = document.getElementById('jobScheduleDayOfMonth');

    if (!form || !btnSave) return;

    // Listener para Programación
    if (jobSched) {
        jobSched.addEventListener('change', () => {
            const s = jobSched.value;
            [scheduleIntervalContainer, scheduleCronContainer, scheduleTimeContainer, 
             scheduleDayOfWeekContainer, scheduleDayOfMonthContainer].forEach(el => {
                if(el) el.classList.add('hidden');
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

    // Listener para Tipo de BD
    if (dbType) {
        dbType.addEventListener('change', () => {
            const t = dbType.value;
            if (t === 'sqlite' || t === 'folder' || t === 'mdb') {
                if (dbCredentialsContainer) dbCredentialsContainer.classList.add('hidden');
                if (networkDetails) networkDetails.classList.add('hidden');
                if (dbFilePathContainer) dbFilePathContainer.classList.remove('hidden');
            } else {
                if (dbCredentialsContainer) dbCredentialsContainer.classList.remove('hidden');
                if (networkDetails) networkDetails.classList.remove('hidden');
                if (dbFilePathContainer) dbFilePathContainer.classList.add('hidden');
            }
        });
    }

    // Listener para Destinos
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

    // Botón «Cancelar edición» (se inyecta dinámicamente en setFormEditMode)
    form.addEventListener('click', (e) => {
        if (e.target.closest('#btnCancelEdit')) {
            isFormDirty = false;
            resetFormToCreateMode();
        }
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
        
        let finalDbName = dbName ? dbName.value.trim() || null : null;
        if (dbType.value === 'sqlite' || dbType.value === 'folder' || dbType.value === 'mdb') {
            const dbFilePathEl = document.getElementById('dbFilePath');
            const pathValue = dbFilePathEl ? dbFilePathEl.value.trim() : '';
            if (!pathValue) {
                alert('Debes especificar la ruta absoluta del archivo/carpeta');
                btnSave.classList.add('animate-shake');
                setTimeout(() => btnSave.classList.remove('animate-shake'), 400);
                return;
            }
            finalDbName = pathValue;
        }

        // ── Payload PLANO según esquema del backend ────────────────────────
        // Construir lógica de Schedule y convertir visual a Cron si es necesario
        let finalScheduleType = jobSched ? jobSched.value : 'manual';
        let finalCron = jobScheduleCron ? jobScheduleCron.value.trim() || null : null;
        let finalInterval = jobScheduleInterval ? parseInt(jobScheduleInterval.value) || null : null;

        if (finalScheduleType === 'daily' || finalScheduleType === 'weekly' || finalScheduleType === 'monthly') {
            const timeVal = jobScheduleTime ? jobScheduleTime.value : '';
            const [hourStr, minStr] = timeVal ? timeVal.split(':') : ['02', '00'];
            const hour = parseInt(hourStr) || 0;
            const min = parseInt(minStr) || 0;

            if (finalScheduleType === 'daily') {
                finalCron = `${min} ${hour} * * *`;
            } else if (finalScheduleType === 'weekly') {
                const dow = jobScheduleDayOfWeek ? jobScheduleDayOfWeek.value : '0';
                finalCron = `${min} ${hour} * * ${dow}`;
            } else if (finalScheduleType === 'monthly') {
                const dom = jobScheduleDayOfMonth ? jobScheduleDayOfMonth.value : '1';
                finalCron = `${min} ${hour} ${dom} * *`;
            }
            finalScheduleType = 'cron'; // El backend procesa el custom cron exacto
            finalInterval = null;
        }

        const jobData = {
            name: jobName.value.trim(),
            description: jobDesc ? jobDesc.value.trim() || null : null,
            db_type: dbType.value || 'postgresql',
            db_host: dbHost ? dbHost.value.trim() || null : null,
            db_port: dbPort ? parseInt(dbPort.value) || null : null,
            db_name: finalDbName,
            db_user: dbUser ? dbUser.value.trim() || null : null,
            db_password: dbPassword && dbPassword.value ? dbPassword.value : undefined,
            schedule: finalScheduleType,
            schedule_interval_minutes: finalInterval,
            schedule_cron: finalCron,
            dest_type: destType ? destType.value : 'local',
            dest_local_path: destLocalPath && destLocalPath.value.trim() ? destLocalPath.value.trim() : null,
            dest_gdrive_folder_id: destGDriveFolderId && destGDriveFolderId.value.trim() ? destGDriveFolderId.value.trim() : null,
        };
        // Limpiar claves con undefined (no enviar la clave si está vacía)
        Object.keys(jobData).forEach(k => jobData[k] === undefined && delete jobData[k]);

        // [PARCHE DE FUERZA BRUTA] - Asegurar el db_type según la UI visual
        const activeCard = document.querySelector('.discovery-card.border-brand-500');
        if (activeCard && activeCard.dataset.engine === 'folder') {
            jobData.db_type = 'folder';
        }

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
            isFormDirty = false; // Reset de dirty al guardar con éxito (o error, pero asume flow completo)
        }
    });
}

/**
 * Rellena el formulario con los datos del job y activa el modo edición.
 * @param {Event} event
 */
function handleEditJob(event) {
    if (isFormDirty) {
        const confirmDiscard = confirm("Tienes cambios sin guardar. ¿Estás seguro de que quieres descartarlos para editar este Job?");
        if (!confirmDiscard) return;
    }

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
        schedule_interval_minutes: btn.dataset.scheduleInterval || '',
        schedule_cron: btn.dataset.scheduleCron || '',
        dest_type: btn.dataset.destType || 'local',
        dest_local_path: btn.dataset.destLocalPath || '',
        dest_gdrive_folder_id: btn.dataset.destGdriveFolderId || '',
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
    const jobDesc = document.getElementById('jobDescription');
    const jobSched = document.getElementById('jobSchedule');
    const dbHost = document.getElementById('dbHost');
    const dbPort = document.getElementById('dbPort');
    const dbName = document.getElementById('dbName');
    const dbUser = document.getElementById('dbUser');
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
    if (dbUser) dbUser.value = extra.db_user || '';
    // La contraseña NO se precarga por seguridad

    // Poblar correctamente dbName o dbFilePath según el tipo
    const dbFilePathEl = document.getElementById('dbFilePath');
    if (extra.db_type === 'sqlite' || extra.db_type === 'folder' || extra.db_type === 'mdb') {
        if (dbFilePathEl) dbFilePathEl.value = extra.db_name || '';
        if (dbName) dbName.value = ''; // limpiar el de red
    } else {
        if (dbName) dbName.value = extra.db_name || '';
        if (dbFilePathEl) dbFilePathEl.value = ''; // limpiar el de fichero
    }

    // Decodificar el cron a formato visual (reverse parse)
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

    // Rellenar campo de programación
    if (jobSched) jobSched.value = displaySchedule;
    
    const jobScheduleInterval = document.getElementById('jobScheduleInterval');
    const jobScheduleCron = document.getElementById('jobScheduleCron');
    const jobScheduleTime = document.getElementById('jobScheduleTime');
    const jobScheduleDayOfWeek = document.getElementById('jobScheduleDayOfWeek');
    const jobScheduleDayOfMonth = document.getElementById('jobScheduleDayOfMonth');

    if (jobScheduleInterval) jobScheduleInterval.value = extra.schedule_interval_minutes || '';
    if (jobScheduleCron) jobScheduleCron.value = displaySchedule === 'cron' ? displayCron : '';
    if (jobScheduleTime && displayTime) jobScheduleTime.value = displayTime;
    if (jobScheduleDayOfWeek && displayDow) jobScheduleDayOfWeek.value = displayDow;
    if (jobScheduleDayOfMonth && displayDom) jobScheduleDayOfMonth.value = displayDom;

    // Rellenar Destinos
    const destType = document.getElementById('destType');
    const destLocalPath = document.getElementById('destLocalPath');
    const destGDriveFolderId = document.getElementById('destGDriveFolderId');
    if (destType) destType.value = extra.dest_type || 'local';
    if (destLocalPath) destLocalPath.value = extra.dest_local_path || '';
    if (destGDriveFolderId) destGDriveFolderId.value = extra.dest_gdrive_folder_id || '';
    
    // Disparar eventos para ocultar/mostrar secciones de destino, programación y base de datos
    if (dbType) dbType.dispatchEvent(new Event('change'));
    if (destType) destType.dispatchEvent(new Event('change'));
    if (jobSched) jobSched.dispatchEvent(new Event('change'));

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
        cancelBtn.className = 'ml-2 px-4 py-2.5 rounded-lg text-sm font-medium border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-surface-800 transition-colors';
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
    
    // Limpiar selección visual (Discovery)
    document.querySelectorAll('.discovery-card').forEach(c => {
        c.classList.remove('border-brand-500', 'bg-brand-500/10', 'dark:bg-brand-500/10', 'bg-brand-500/5');
        c.classList.add('border-slate-300', 'dark:border-slate-700', 'bg-white', 'dark:bg-surface-950');
    });

    isFormDirty = false;
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
    errorText.className = 'error-message text-red-500 text-xs mt-1';
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
                loadHistory(true),
                loadStats(true)
            ]);
        } catch (error) {
            console.warn('Polling error (silenciado):', error);
        }
    }, 8000);
}

/**
 * Carga las estadísticas del Dashboard (Centro de Mando).
 * Actualiza los widgets de Total Jobs, Tasa de Éxito y Espacio Ocupado.
 * @param {boolean} isSilent - Si es true, silencia los errores en la UI.
 */
async function loadStats(isSilent = false) {
    const elTotal = document.getElementById('stat-total-jobs');

    // Si los elementos no existen en el DOM, no hacer nada
    if (!elTotal) return;

    try {
        const stats = await api.getStats();
        elTotal.textContent = stats.total_jobs !== undefined ? stats.total_jobs : 'N/A';
    } catch (error) {
        if (!isSilent) {
            console.error('Error cargando estadísticas:', error);
            elTotal.textContent = 'N/A';
        }
    }
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
    toast.className = `toast toast-${type} bg-white dark:bg-[#1e293b] text-slate-800 dark:text-white border shadow-lg`;
    if(type === 'success') toast.classList.add('border-green-500');
    else toast.classList.add('border-red-500');

    const icon = type === 'success'
        ? '<i class="fa-solid fa-circle-check text-lg text-green-500"></i>'
        : '<i class="fa-solid fa-circle-exclamation text-lg text-red-500"></i>';

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
        '  <span class="text-slate-600 dark:text-slate-400">Cargando logs...</span>',
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
            '<span class="log-line-error text-red-500">[ERROR] No se pudieron cargar los logs.</span>\n',
            `<span class="log-line-error text-red-500">Detalle: ${escapeHtml(String(error.message))}</span>\n`,
            '<span class="log-line-default text-slate-600 dark:text-slate-400">Verifica que el endpoint GET /api/v1/history/{runId}/logs esté disponible.</span>'
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
        : String(rawLogs).split('\\n');

    if (lines.length === 0 || (lines.length === 1 && lines[0].trim() === '')) {
        outputEl.innerHTML = '<span class="log-line-default text-slate-600 dark:text-slate-400">(sin logs disponibles)</span>';
        return;
    }

    // Colorizar cada línea según el nivel
    outputEl.innerHTML = lines.map(line => {
        const safe = escapeHtml(line);
        const upper = line.toUpperCase();

        if (upper.includes('[SUCCESS]') || upper.includes('SUCCESS')) return `<span class="text-green-500 font-medium">${safe}</span>`;
        if (upper.includes('[ERROR]') || upper.includes('ERROR')) return `<span class="text-red-500 font-medium">${safe}</span>`;
        if (upper.includes('[WARN]') || upper.includes('WARNING')) return `<span class="text-yellow-500 font-medium">${safe}</span>`;
        if (upper.includes('[INFO]') || upper.includes('[DEBUG]')) return `<span class="text-brand-500 font-medium">${safe}</span>`;
        return `<span class="text-slate-600 dark:text-slate-400">${safe}</span>`;
    }).join('\\n');

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

    // Rellenar zona horaria actual automáticamente si no tiene valor
    const tzSelect = document.getElementById('s-timezone');
    if (tzSelect) {
        const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        tzSelect.innerHTML = `<option value="${userTz}">${userTz}</option>`;
        tzSelect.value = userTz;
        tzSelect.setAttribute('readonly', 'true');
        tzSelect.style.pointerEvents = 'none';
        tzSelect.classList.add('bg-slate-100', 'dark:bg-slate-800', 'opacity-80');
    }

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
    if (saveBtn) saveBtn.addEventListener('click', (e) => {
        e.preventDefault();
        handleSaveSettings(false);
    });

    // ── Enviar Email de Prueba ──────────────────────────────
    const btnTestEmail = document.getElementById('btnTestEmail');
    if (btnTestEmail) {
        btnTestEmail.addEventListener('click', async (e) => {
            e.preventDefault();
            
            // Requerido por el usuario: Mostrar alert
            alert('Enviando correo de prueba. Por favor espera...');
            
            btnTestEmail.disabled = true;
            const originalHtml = btnTestEmail.innerHTML;
            btnTestEmail.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enviando...';
            try {
                // Guardar antes por si ha cambiado el email en la interfaz
                await handleSaveSettings(true); 
                
                const response = await fetch('/api/v1/settings/test-email', { method: 'POST' });
                const result = await response.json();
                
                if (response.ok && result.success) {
                    alert('ÉXITO: ' + result.message);
                } else {
                    alert('ERROR: ' + (result.message || result.detail || 'Fallo desconocido al enviar email'));
                }
            } catch (err) {
                console.error(err);
                alert('ERROR CRÍTICO: No se pudo contactar con el servidor. Revisa la consola.');
            } finally {
                btnTestEmail.disabled = false;
                btnTestEmail.innerHTML = originalHtml;
            }
        });
    }
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
    set('s-language', s.language || 'es');
    set('s-admin-email', s.admin_email);
    // set('s-timezone', s.timezone); // Se detecta localmente ahora
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
async function handleSaveSettings(silent = false) {
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
        language: get('s-language') || 'es',
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
        if (!silent) {
            alert('✅ Ajustes guardados correctamente');
            applyTranslations(payload.language);
            closeSettingsModal();
            setTimeout(() => { location.reload(); }, 500);
        }
    } catch (err) {
        console.error('Error al guardar los ajustes:', err);
        if (!silent) alert('❌ Error al guardar los ajustes. Revisa la consola.');
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Guardar cambios';
    }
}

// ============================================================================
// AUTO-DESCUBRIMIENTO DE BASES DE DATOS
// ============================================================================

/**
 * Llama a la API de autodescubrimiento y dibuja las tarjetas dinámicamente.
 */
async function loadDiscovery() {
    const container = document.getElementById('discoveryContainer');
    if (!container) return;

    try {
        const response = await fetch('/api/v1/jobs/discovery');
        if (!response.ok) throw new Error('Error al escanear red');
        const services = await response.json();

        services.forEach(svc => {
            const card = document.createElement('div');
            card.className = 'discovery-card cursor-pointer border border-slate-300 dark:border-slate-700 bg-white dark:bg-surface-950 hover:border-brand-500 dark:hover:border-brand-500 hover:bg-brand-50 rounded-lg p-4 transition-all';
            card.dataset.engine = svc.engine;
            card.dataset.host = svc.host;
            card.dataset.port = svc.port;
            card.dataset.name = svc.name;
            
            card.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-500 dark:text-brand-400 pointer-events-none">
                        <i class="fa-solid fa-server"></i>
                    </div>
                    <div class="pointer-events-none">
                        <p class="text-sm font-semibold text-slate-800 dark:text-white">${svc.name}</p>
                        <p class="text-xs text-brand-500 dark:text-brand-400 font-mono">${svc.host}:${svc.port}</p>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });

        // Añadir event listeners a todas las tarjetas (incluyendo la estática)
        document.querySelectorAll('.discovery-card').forEach(card => {
            card.addEventListener('click', handleDiscoveryClick);
        });

    } catch (error) {
        console.error('Error en autodescubrimiento:', error);
        // Asegurar que la tarjeta estática funcione aunque falle la API
        document.querySelectorAll('.discovery-card').forEach(card => {
            card.addEventListener('click', handleDiscoveryClick);
        });
    }
}

/**
 * Maneja el clic en una tarjeta de descubrimiento, autocompletando el formulario.
 */
function handleDiscoveryClick(event) {
    const card = event.currentTarget;
    const engine = card.dataset.engine;

    // Resaltar tarjeta seleccionada visualmente
    document.querySelectorAll('.discovery-card').forEach(c => {
        c.classList.remove('border-brand-500', 'bg-brand-50', 'dark:bg-brand-500/10', 'ring-1', 'ring-brand-500');
    });
    card.classList.add('border-brand-500', 'bg-brand-50', 'dark:bg-brand-500/10', 'ring-1', 'ring-brand-500');

    // Elementos del formulario
    const dbTypeEl = document.getElementById('dbType');
    const dbHostEl = document.getElementById('dbHost');
    const dbPortEl = document.getElementById('dbPort');
    const dbUserEl = document.getElementById('dbUser');
    const dbNameEl = document.getElementById('dbName');
    const dbFilePathContainer = document.getElementById('dbFilePathContainer');
    const dbCredentialsContainer = document.getElementById('dbCredentialsContainer');
    const networkDetails = document.querySelector('details.group');

    if (engine === 'sqlite' || engine === 'folder' || engine === 'mdb') {
        // Fichero Local o Carpeta
        if (dbTypeEl) {
            dbTypeEl.value = engine;
            dbTypeEl.dispatchEvent(new Event('change'));
        }
        if (dbHostEl) dbHostEl.value = '';
        if (dbPortEl) dbPortEl.value = '';
        
        if (dbCredentialsContainer) dbCredentialsContainer.classList.add('hidden');
        if (networkDetails) networkDetails.classList.add('hidden');
        if (dbFilePathContainer) dbFilePathContainer.classList.remove('hidden');
        
        // Foco en la ruta del archivo/carpeta
        const dbFilePathEl = document.getElementById('dbFilePath');
        if (dbFilePathEl) dbFilePathEl.focus();

    } else {
        // Motor de Base de Datos en Red (Autodescubierto)
        if (dbTypeEl) {
            dbTypeEl.value = engine;
            dbTypeEl.dispatchEvent(new Event('change'));
        }
        if (dbHostEl) dbHostEl.value = card.dataset.host || '127.0.0.1';
        if (dbPortEl) dbPortEl.value = card.dataset.port || '';
        
        if (dbCredentialsContainer) dbCredentialsContainer.classList.remove('hidden');
        if (networkDetails) networkDetails.classList.remove('hidden');
        if (dbFilePathContainer) dbFilePathContainer.classList.add('hidden');

        // Ajustar placeholder del usuario como sugerencia
        if (dbUserEl) {
            if (engine === 'postgresql') dbUserEl.placeholder = 'Ej: postgres';
            else if (engine === 'sqlserver') dbUserEl.placeholder = 'Ej: sa';
            else if (engine === 'mysql') dbUserEl.placeholder = 'Ej: root';
            else dbUserEl.placeholder = 'Usuario';
        }

        // Dar foco automáticamente al Nombre de la Base de Datos para seguir el flujo
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
    if (!authBox || !pickerBox) return;

    try {
        const res = await fetch('/api/v1/auth/google/status');
        const data = await res.json();
        
        if (data.authorized) {
            authBox.classList.add('hidden');
            pickerBox.classList.remove('hidden');
        } else {
            authBox.classList.remove('hidden');
            pickerBox.classList.add('hidden');
        }
    } catch (e) {
        console.error("Error chequeando estado de Google Drive", e);
    }
}

document.getElementById('btnConnectDrive')?.addEventListener('click', () => {
    // Abrir popup de login
    const w = 500;
    const h = 600;
    const left = (screen.width/2)-(w/2);
    const top = (screen.height/2)-(h/2);
    window.open('/api/v1/auth/google/login', 'GDrive Auth', `width=${w},height=${h},top=${top},left=${left}`);
});

// Escuchar mensaje del popup cuando termina el login
window.addEventListener("message", (event) => {
    if (event.data === "GOOGLE_AUTH_SUCCESS") {
        checkGoogleDriveStatus();
    }
});

document.getElementById('btnDisconnectDrive')?.addEventListener('click', async () => {
    if (!confirm("¿Seguro que quieres desvincular la cuenta de Google Drive?")) return;
    
    try {
        const res = await fetch('/api/v1/auth/google/disconnect', { method: 'DELETE' });
        if (res.ok) {
            showToast("Cuenta de Google Drive desvinculada", "success");
            checkGoogleDriveStatus();
            
            // Limpiar campos visuales
            const destGDriveFolderId = document.getElementById('destGDriveFolderId');
            const destGDriveFolderName = document.getElementById('destGDriveFolderName');
            if (destGDriveFolderId) destGDriveFolderId.value = '';
            if (destGDriveFolderName) destGDriveFolderName.value = '';
        } else {
            showToast("Error al desvincular la cuenta", "error");
        }
    } catch (e) {
        console.error("Error al desvincular", e);
        showToast("Error de conexión", "error");
    }
});

// Cuando la API de google se cargue, llamar a loadPicker()
function loadGoogleApi() {
    gapi.load('picker', { 'callback': onPickerApiLoad });
}
function onPickerApiLoad() {
    pickerApiLoaded = true;
}

// Interceptar carga global de script si gapi ya existe
const gapiInterval = setInterval(() => {
    if (typeof gapi !== 'undefined') {
        clearInterval(gapiInterval);
        loadGoogleApi();
    }
}, 100);

document.getElementById('btnSelectDriveFolder')?.addEventListener('click', async () => {
    if (!pickerApiLoaded) {
        showToast("La API de Google Picker aún se está cargando...", "error");
        return;
    }

    try {
        // Pedir token temporal al backend
        const res = await fetch('/api/v1/auth/google/token');
        if (!res.ok) throw new Error("No se pudo obtener el token");
        
        const data = await res.json();
        gdriveAccessToken = data.access_token;
        gdriveClientId = data.client_id;
        
        createPicker();
    } catch (e) {
        console.error(e);
        showToast("Error al abrir el explorador de Drive. ¿Estás conectado?", "error");
    }
});

function createPicker() {
    if (!gdriveAccessToken) return;
    
    // Crear la vista solo de carpetas
    const view = new google.picker.DocsView(google.picker.ViewId.FOLDERS);
    view.setIncludeFolders(true);
    view.setSelectFolderEnabled(true);
    view.setMimeTypes('application/vnd.google-apps.folder');

    const picker = new google.picker.PickerBuilder()
        .enableFeature(google.picker.Feature.NAV_HIDDEN)
        .enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
        // .setAppId(gdriveClientId.split('-')[0]) // Opcional
        .setOAuthToken(gdriveAccessToken)
        .addView(view)
        .setTitle("Selecciona la carpeta para los backups")
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
        
        showToast(`Carpeta "${folderName}" seleccionada`, "success");
    }
}

/**
 * Carga los logs reales de una ejecución desde la API y los pinta en la terminal inferior
 * @param {string} runId 
 */
async function loadTerminalLogs(runId) {
    const terminal = document.getElementById('bottomLogsTerminal');
    if (!terminal) return;

    terminal.innerHTML = '<span class="text-slate-500 italic">Cargando logs... <i class="fa-solid fa-circle-notch fa-spin"></i></span>';

    try {
        const res = await fetch(`/api/v1/history/${runId}/logs`);
        if (!res.ok) throw new Error("No se pudieron cargar los logs");
        
        const data = await res.json();
        const logs = data.logs || "No hay logs disponibles para esta ejecución.";
        
        terminal.innerHTML = ''; // Limpiar
        
        // Pintar por líneas para añadir colorines
        const lines = Array.isArray(logs) ? logs : String(logs).split('\\n');
        lines.forEach(line => {
            const div = document.createElement('div');
            div.textContent = line;
            
            // Coloreado sintáctico simple de logs
            if (line.includes('[SUCCESS]')) div.className = 'text-green-500 font-medium';
            else if (line.includes('[ERROR]') || line.includes('[CRITICAL]')) div.className = 'text-red-500 font-medium';
            else if (line.includes('[WARNING]')) div.className = 'text-yellow-500';
            else if (line.includes('[INFO]')) div.className = 'text-brand-500';
            else div.className = 'text-slate-600 dark:text-slate-400';
            
            terminal.appendChild(div);
        });

        // Autoscroll al final
        terminal.scrollTop = terminal.scrollHeight;
        
    } catch (e) {
        console.error("Error cargando logs:", e);
        terminal.innerHTML = '<span class="text-red-500 italic">Error al cargar los logs.</span>';
    }
}

// ============================================================================
// SISTEMA DE TRADUCCIÓN (i18n)
// ============================================================================

const i18n = {
    es: {
        "Nuevo Job de Backup": "Nuevo Job de Backup",
        "Nombre del Job": "Nombre del Job",
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
        "Trabajos (Jobs)": "Trabajos (Jobs)",
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
        "Vincular con Google": "Vincular con Google",
        "Desvincular Google Drive": "Desvincular Google Drive"
    },
    en: {
        "Nuevo Job de Backup": "New Backup Job",
        "Nombre del Job": "Job Name",
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
        "Trabajos (Jobs)": "Backup Jobs",
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
        "Vincular con Google": "Link with Google",
        "Desvincular Google Drive": "Unlink Google Drive"
    }
};

function applyTranslations(lang) {
    if (!i18n[lang]) lang = 'es';
    const dict = i18n[lang];
    
        const elementsToTranslate = [
        ...document.querySelectorAll('h3, label, p.text-sm, span, summary span, th, .btn-run, .btn-edit, .btn-delete')
    ];
    
    elementsToTranslate.forEach(el => {
        if (!el.dataset.originalText) {
            if (el.children.length === 0 || el.tagName.toLowerCase() === 'label') {
                el.dataset.originalText = el.textContent.trim();
            }
        }
        
        const original = el.dataset.originalText;
        if (original && dict[original]) {
            el.textContent = dict[original];
        }
    });
    
    document.querySelectorAll('option').forEach(opt => {
        if (!opt.dataset.originalText) opt.dataset.originalText = opt.textContent.trim();
        const original = opt.dataset.originalText;
        if (original && dict[original]) {
            opt.textContent = dict[original];
        }
    });
}

// Interceptar populateSettingsForm para aplicar idioma guardado
const originalPopulateSettingsForm = populateSettingsForm;
populateSettingsForm = function(s) {
    originalPopulateSettingsForm(s);
    if (s.language) {
        applyTranslations(s.language);
    }
};

// Escuchar cambios en el selector de idioma en vivo
document.getElementById('s-language')?.addEventListener('change', (e) => {
    applyTranslations(e.target.value);
});

// ====== LÓGICA DEL ESCÁNER DE ESPACIO ======
// ====== LÓGICA DEL ESCÁNER DE ESPACIO ======
let scanTimeout;
async function scanFreeSpace(path) {
    const statEl = document.getElementById('stat-free-space');
    const icon = document.getElementById('iconScanSpace');
    if (!statEl || !icon) return;

    if (!path) {
        statEl.textContent = 'Esperando ruta...';
        return;
    }
    
    icon.classList.add('fa-spin');
    statEl.textContent = 'Escaneando...';
    
    try {
        const data = await api.getFreeSpace(path);
        let space = data.free_space_mb;
        let unit = 'MB';
        if (space > 1024) {
            space = (space / 1024).toFixed(2);
            unit = 'GB';
        }
        statEl.textContent = `${space} ${unit} Libres`;
    } catch (error) {
        statEl.textContent = 'Error al leer';
        console.warn(`No se pudo escanear la ruta: ${error.message}`);
    } finally {
        icon.classList.remove('fa-spin');
    }
}

// Escuchar cambios en el input de destino (con debounce para no saturar la API)
const destLocalInput = document.getElementById('destLocalPath');
if (destLocalInput) {
    destLocalInput.addEventListener('input', (e) => {
        clearTimeout(scanTimeout);
        scanTimeout = setTimeout(() => {
            scanFreeSpace(e.target.value.trim());
        }, 800);
    });
    // Escanear si ya hay un valor cargado
    if (destLocalInput.value.trim()) {
        scanFreeSpace(destLocalInput.value.trim());
    }
}

// ====== LÓGICA DEL EXPLORADOR DE ARCHIVOS WEB ======
let currentExplorerInput = null;
let currentExplorerPath = "";

async function openFileExplorer(inputId) {
    currentExplorerInput = document.getElementById(inputId);
    const modal = document.getElementById('fileExplorerModal');
    modal.classList.remove('hidden');
    await renderExplorerPath(""); // Carga discos inicialmente
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
        
        pathDisplay.textContent = data.current_path || "Este equipo";
        btnUp.disabled = !data.parent_path;
        btnUp.onclick = () => renderExplorerPath(data.parent_path);
        
        let html = '';
        if (data.folders.length === 0 && data.files.length === 0) {
            html = '<div class="text-center py-8 text-slate-500 text-sm">Carpeta vacía</div>';
        } else {
            // Renderizar carpetas
            data.folders.forEach(f => {
                html += `
                    <div class="explorer-item flex items-center gap-3 p-2 hover:bg-slate-200 dark:hover:bg-surface-800 rounded cursor-pointer transition-colors" data-path="${f.path.replace(/\\/g, '\\\\')}">
                        <i class="fa-solid fa-folder text-brand-400 text-lg w-5 text-center"></i>
                        <span class="text-sm text-slate-700 dark:text-slate-300 select-none truncate">${f.name}</span>
                    </div>
                `;
            });
            // Renderizar archivos
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
        
        // Listeners
        container.querySelectorAll('.explorer-item').forEach(item => {
            item.addEventListener('click', () => {
                const targetPath = item.dataset.path;
                if (item.querySelector('.fa-folder')) {
                    renderExplorerPath(targetPath);
                } else {
                    currentExplorerPath = targetPath;
                    pathDisplay.textContent = targetPath;
                    // Resaltar seleccionado
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
        // Disparar el evento input para que el escáner (u otros listeners) se enteren del cambio
        currentExplorerInput.dispatchEvent(new Event('input'));
    }
    closeFileExplorer();
});

document.getElementById('btnExplorerCancel')?.addEventListener('click', closeFileExplorer);
document.getElementById('btnCloseExplorer')?.addEventListener('click', closeFileExplorer);
document.getElementById('btnExplorerRefresh')?.addEventListener('click', () => renderExplorerPath(currentExplorerPath));

