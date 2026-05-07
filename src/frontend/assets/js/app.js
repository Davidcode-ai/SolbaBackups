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
});

/**
 * Carga la lista de Jobs desde la API y los renderiza en la pantalla central.
 */
async function loadJobs(isSilent = false) {
    const container = document.getElementById('jobs-container');
    if (!container) return;

    try {
        // Llama al método getJobs() definido en api.js
        const jobs = await api.getJobs();
        
        // Limpiamos el contenido estático
        container.innerHTML = ''; 

        if (jobs.length === 0) {
            container.innerHTML = '<p class="text-slate-400">No hay jobs configurados.</p>';
            return;
        }

        // Pintamos cada job
        jobs.forEach(job => {
            const jobCard = document.createElement('div');
            jobCard.className = 'bg-surface-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4';
            
            jobCard.innerHTML = `
                <div>
                    <div class="flex items-center gap-3 mb-1">
                        <div class="w-8 h-8 rounded-lg bg-brand-500/10 text-brand-400 flex items-center justify-center">
                            <i class="fa-solid fa-server"></i>
                        </div>
                        <h3 class="text-lg font-semibold text-white">${job.name || 'Job sin nombre'}</h3>
                    </div>
                    <p class="text-sm text-slate-400 mt-2">${job.description || 'Sin descripción'} • Schedule: ${job.schedule || 'Manual'}</p>
                </div>
                <div>
                    <button class="btn-ejecutar bg-brand-500 hover:bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm flex items-center" data-id="${job.id}">
                        <i class="fa-solid fa-play mr-1.5"></i> <span>Ejecutar</span>
                    </button>
                </div>
            `;
            container.appendChild(jobCard);
        });

        // 3. Asignar EventListener a cada botón de "Ejecutar"
        document.querySelectorAll('.btn-ejecutar').forEach(btn => {
            btn.addEventListener('click', handleRunJob);
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

            const historyItem = document.createElement('div');
            historyItem.className = `bg-surface-800 border rounded-lg p-3 cursor-pointer transition-colors ${borderClass}`;
            
            historyItem.innerHTML = `
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-semibold text-slate-300">${dateStr}</span>
                    <span class="px-2 py-0.5 rounded text-[10px] font-bold ${statusClass} border uppercase tracking-wide">
                        ${record.status}
                    </span>
                </div>
                <div class="flex items-center gap-4 text-xs text-slate-400">
                    <div class="flex items-center gap-1.5">
                        <i class="fa-solid fa-server"></i> Job ID: ${record.job_id || 'N/A'}
                    </div>
                </div>
                ${!isSuccess && record.error_message ? `<p class="text-[11px] text-red-400 truncate mt-2">Error: ${record.error_message}</p>` : ''}
            `;
            
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
 * Inicializa la validación del formulario de creación de Jobs.
 */
function initJobFormValidation() {
    const form = document.getElementById('createJobForm');
    const btnSave = document.getElementById('btnSaveJob');
    const jobName = document.getElementById('jobName');
    const dbType = document.getElementById('dbType');

    if (!form || !btnSave) return;

    btnSave.addEventListener('click', async (e) => {
        e.preventDefault(); // Detenemos el envío estándar
        let isValid = true;

        // 1. Limpiamos errores previos en cada intento
        clearErrors(jobName);
        clearErrors(dbType);

        // 2. Comprobamos 'Nombre del Job'
        if (jobName.value.trim() === '') {
            showError(jobName, 'Este campo es obligatorio');
            isValid = false;
        }

        // 3. Comprobamos 'Base de Datos'
        if (dbType.value.trim() === '') {
            showError(dbType, 'Debes seleccionar un motor de BD');
            isValid = false;
        }

        // 4. Si hay algún error, paramos la ejecución y animamos el botón
        if (!isValid) {
            btnSave.classList.add('animate-shake');
            // Removemos la clase luego de 400ms para poder repetir la animación en el futuro
            setTimeout(() => btnSave.classList.remove('animate-shake'), 400);
            return;
        }

        // --- TODO ES VÁLIDO: Aquí harías tu llamada real a la API ---
        btnSave.disabled = true;
        btnSave.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';
        
        try {
            await api.createJob({
                name: jobName.value.trim(),
                description: dbType.value,
                schedule: 'Manual'
            });
            showToast('¡Job creado con éxito!', 'success');
            form.reset();
            loadJobs(); // Recargar la lista de jobs visualmente
        } catch (error) {
            showToast('Error al guardar el Job. Revisa la consola.', 'error');
        } finally {
            btnSave.disabled = false;
            btnSave.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Guardar Configuración';
        }
    });
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
