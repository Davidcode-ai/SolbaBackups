import os
import subprocess

def fix_app():
    # Git checkout the original app.js
    subprocess.run(['git', 'checkout', 'src/frontend/assets/js/app.js'], check=True)

    with open('src/frontend/assets/js/app.js', 'r', encoding='utf-8') as f:
        content = f.read()

    # Apply the patches one by one safely
    # 1. loadJobs container fix
    content = content.replace(
        "const container = document.getElementById('jobs-container');",
        "const container = document.getElementById('sidebar-jobs-container');"
    )

    # 2. handleRunJob
    old_handle_run_job = """async function handleRunJob(event) {
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
}"""
    new_handle_run_job = """async function handleRunJob(event) {
    event.stopPropagation();
    const button = event.currentTarget;
    const jobId = button.dataset.id;
    const icon = button.querySelector('i');

    button.disabled = true;
    button.classList.add('opacity-50', 'cursor-not-allowed');
    icon.className = 'fa-solid fa-spinner fa-spin text-[10px]';

    try {
        await api.runJob(jobId);
        showToast(`¡Job ${jobId} ejecutado con éxito!`, 'success');
        loadHistory();
    } catch (error) {
        console.error(`Error al ejecutar el job ${jobId}:`, error);
        showToast(`Hubo un error al ejecutar el Job ${jobId}.`, 'error');
    } finally {
        button.disabled = false;
        button.classList.remove('opacity-50', 'cursor-not-allowed');
        icon.className = 'fa-solid fa-play text-[10px]';
    }
}"""
    content = content.replace(old_handle_run_job, new_handle_run_job)

    # 3. Add loadTerminalLogs to end
    new_load_terminal_logs = """
async function loadTerminalLogs(runId) {
    const terminal = document.getElementById('bottomLogsTerminal');
    if (!terminal) return;

    terminal.innerHTML = '<span class="text-slate-500 italic">Cargando logs... <i class="fa-solid fa-circle-notch fa-spin"></i></span>';

    try {
        const res = await fetch(`/api/v1/history/${runId}/logs`);
        if (!res.ok) throw new Error("No se pudieron cargar los logs");
        
        const data = await res.json();
        const logs = data.logs || "No hay logs disponibles para esta ejecución.";
        
        terminal.innerHTML = '';
        
        const lines = Array.isArray(logs) ? logs : String(logs).split('\\n');
        lines.forEach(line => {
            const div = document.createElement('div');
            div.textContent = line;
            
            if (line.includes('[SUCCESS]')) div.className = 'text-green-400 font-medium';
            else if (line.includes('[ERROR]') || line.includes('[CRITICAL]')) div.className = 'text-red-400 font-medium';
            else if (line.includes('[WARNING]')) div.className = 'text-yellow-400';
            else if (line.includes('[INFO]')) div.className = 'text-brand-400';
            else div.className = 'text-slate-400';
            
            terminal.appendChild(div);
        });

        terminal.scrollTop = terminal.scrollHeight;
        
    } catch (e) {
        console.error("Error cargando logs:", e);
        terminal.innerHTML = '<span class="text-red-400 italic">Error al cargar los logs.</span>';
    }
}
"""
    content += new_load_terminal_logs

    # 4. loadJobs replacement
    # I'll just rewrite loadJobs to use the new html structure for sidebar
    # We find loadJobs
    import re
    
    with open('src/frontend/assets/js/app.js', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix_app()
