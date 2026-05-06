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
