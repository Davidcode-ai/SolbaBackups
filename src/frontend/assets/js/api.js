/**
 * ApiClient para manejar la comunicación con el backend (FastAPI).
 * Esta clase proporciona métodos limpios y asíncronos para interactuar con la API REST.
 */
class ApiClient {
    constructor(baseUrl = '/api/v1') {
        this.baseUrl = baseUrl;
    }

    /**
     * Obtiene la lista de trabajos (jobs) desde el servidor.
     * @returns {Promise<Array>} Lista de trabajos
     */
    async getJobs() {
        try {
            const response = await fetch(`${this.baseUrl}/jobs`);
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error en getJobs:', error);
            throw error;
        }
    }

    /**
     * Obtiene el historial de ejecuciones.
     * @returns {Promise<Array>} Historial de ejecuciones
     */
    async getHistory() {
        try {
            const response = await fetch(`${this.baseUrl}/history`);
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error en getHistory:', error);
            throw error;
        }
    }

    /**
     * Crea un nuevo trabajo enviando los datos al servidor.
     * @param {Object} jobData - Datos del formulario del nuevo trabajo
     * @returns {Promise<Object>} El trabajo creado
     */
    async createJob(jobData) {
        try {
            const response = await fetch(`${this.baseUrl}/jobs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(jobData)
            });
            
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error en createJob:', error);
            throw error;
        }
    }

    /**
     * Ejecuta un trabajo específico por su ID.
     * @param {string|number} jobId - El ID del trabajo a ejecutar
     * @returns {Promise<Object>} Resultado de la ejecución
     */
    async runJob(jobId) {
        try {
            const response = await fetch(`${this.baseUrl}/jobs/${jobId}/run`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`Error en runJob (ID: ${jobId}):`, error);
            throw error;
        }
    }

    /**
     * Obtiene los logs de una ejecución específica del historial.
     * @param {string|number} runId - El ID del run/ejecución a consultar
     * @returns {Promise<Object>} Objeto con los logs de la ejecución { logs: string }
     */
    async getRunLogs(runId) {
        try {
            const response = await fetch(`${this.baseUrl}/history/${runId}/logs`);
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`Error en getRunLogs (run ID: ${runId}):`, error);
            throw error;
        }
    }

    /**
     * Actualiza un trabajo existente (PUT).
     * @param {string|number} jobId  - El ID del trabajo a actualizar
     * @param {Object}        jobData - Datos actualizados del trabajo
     * @returns {Promise<Object>} El trabajo actualizado
     */
    async updateJob(jobId, jobData) {
        try {
            const response = await fetch(`${this.baseUrl}/jobs/${jobId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(jobData)
            });
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`Error en updateJob (ID: ${jobId}):`, error);
            throw error;
        }
    }

    /**
     * Elimina un trabajo por su ID (DELETE).
     * @param {string|number} jobId - El ID del trabajo a eliminar
     * @returns {Promise<Object>} Respuesta del servidor
     */
    async deleteJob(jobId) {
        try {
            const response = await fetch(`${this.baseUrl}/jobs/${jobId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status}`);
            }
            // 204 No Content no tiene body — devolvemos vacío
            return response.status === 204 ? {} : await response.json();
        } catch (error) {
            console.error(`Error en deleteJob (ID: ${jobId}):`, error);
            throw error;
        }
    }

    /**
     * Obtiene los ajustes globales de la aplicación.
     * @returns {Promise<Object>} Objeto con la configuración actual
     */
    async getSettings() {
        try {
            const response = await fetch(`${this.baseUrl}/settings`);
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error en getSettings:', error);
            throw error;
        }
    }

    /**
     * Guarda los ajustes globales (PUT; fallback a POST si el servidor devuelve 405).
     * @param {Object} settingsData - Objeto con los ajustes a guardar
     * @returns {Promise<Object>} Configuración guardada
     */
    async saveSettings(settingsData) {
        const send = async (method) => fetch(`${this.baseUrl}/settings`, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settingsData)
        });

        try {
            let response = await send('PUT');
            // Fallback: si el servidor solo implementó POST
            if (response.status === 405) response = await send('POST');
            if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
            return response.status === 204 ? {} : await response.json();
        } catch (error) {
            console.error('Error en saveSettings:', error);
            throw error;
        }
    }

    /**
     * Obtiene las estadísticas globales del Dashboard.
     * @returns {Promise<Object>} Objeto con las estadísticas (total_jobs, success_rate, storage_used)
     */
    async getStats() {
        try {
            const response = await fetch(`${this.baseUrl}/stats`);
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error en getStats:', error);
            throw error;
        }
    }
    /**
     * Obtiene los discos disponibles en el sistema.
     * @returns {Promise<Object>} Objeto con array de discos { drives: ["C:\\", ...] }
     */
    async getDrives() {
        try {
            const response = await fetch(`${this.baseUrl}/utils/drives`);
            if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error en getDrives:', error);
            throw error;
        }
    }

    /**
     * Lista el contenido de un directorio.
     * @param {string} path - Ruta del directorio
     * @returns {Promise<Object>} Contenido { folders: [...], files: [...] }
     */
    async listDirectory(path = "") {
        try {
            const response = await fetch(`${this.baseUrl}/utils/list-dir?path=${encodeURIComponent(path)}`);
            if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error en listDirectory:', error);
            throw error;
        }
    }

    /**
     * Calcula el espacio libre de un disco o ruta.
     * @param {string} path - Ruta a comprobar
     * @returns {Promise<Object>} { free_space_mb: 1024 }
     */
    async getFreeSpace(path) {
        try {
            const response = await fetch(`${this.baseUrl}/utils/free-space?path=${encodeURIComponent(path)}`);
            if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error en getFreeSpace:', error);
            throw error;
        }
    }
}

// Instancia global para ser usada en otros archivos JS de la aplicación
const api = new ApiClient();

/*
 ==============================================================================
 EJEMPLO DE CÓMO CAPTURAR EVENTOS DEL FORMULARIO HTML (Para futura referencia)
 ==============================================================================

 // 1. Esperamos a que el DOM esté completamente cargado para asegurarnos de que
 //    todos los elementos HTML (como el formulario) existan en la página.
 document.addEventListener('DOMContentLoaded', () => {
     
     // 2. Seleccionamos el formulario de creación (asumiendo que tiene id="jobForm")
     const jobForm = document.getElementById('jobForm');
     
     if (jobForm) {
         // 3. Escuchamos el evento 'submit' del formulario
         jobForm.addEventListener('submit', async (event) => {
             // Prevenimos que la página se recargue (comportamiento por defecto del form)
             event.preventDefault();
             
             // 4. Extraemos los datos del formulario
             const formData = new FormData(jobForm);
             
             // Convertimos FormData a un objeto plano (jobData)
             const jobData = {
                 name: formData.get('name'),
                 schedule: formData.get('schedule'),
                 // ... otros campos del formulario
             };
             
             try {
                 // 5. Usamos nuestra instancia global 'api' para enviar los datos al backend
                 const result = await api.createJob(jobData);
                 console.log('Trabajo creado con éxito:', result);
                 
                 // Opcional: limpiar el formulario y dar feedback al usuario
                 jobForm.reset();
                 alert('Trabajo creado correctamente!');
                 
                 // loadJobsList(); // Aquí llamaríamos a la función para refrescar la lista de trabajos
                 
             } catch (error) {
                 // Manejo de errores en caso de que falle la petición
                 console.error('Hubo un error al crear el trabajo', error);
                 alert('Hubo un error al crear el trabajo. Revisa la consola.');
             }
         });
     }
     
     // -------------------------------------------------------------------------
     // EJEMPLO: Botón para ejecutar un job 
     // Asumiendo que en la tabla hay botones con class="btn-run" y un atributo data-id="123"
     // -------------------------------------------------------------------------
     // document.querySelectorAll('.btn-run').forEach(button => {
     //     button.addEventListener('click', async (e) => {
     //         const jobId = e.target.dataset.id; // Obtenemos el ID desde el atributo data-id
     //         try {
     //             await api.runJob(jobId);
     //             alert(`Trabajo ${jobId} ejecutado con éxito!`);
     //         } catch (error) {
     //             alert('Error al intentar ejecutar el trabajo.');
     //         }
     //     });
     // });
 });
*/
