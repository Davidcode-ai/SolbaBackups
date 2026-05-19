import logging
import subprocess
from typing import Optional

from src.core.models import JobRead

log = logging.getLogger(__name__)

def parse_cron_to_schtasks(cron_expr: str) -> dict:
    """
    Convierte una expresión cron simple (ej. "30 2 * * *") a los argumentos de schtasks.
    Retorna un diccionario con:
    - frequency: "DAILY", "WEEKLY" o "MONTHLY"
    - time: "HH:mm"
    - day: string con el día (ej. "MON", "15") o None
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Expresión cron inválida: {cron_expr}")

    minute = parts[0]
    hour = parts[1]
    dom = parts[2]
    month = parts[3]
    dow = parts[4]

    # Formatear la hora a HH:mm
    st = f"{int(hour):02d}:{int(minute):02d}"

    if dom == '*' and month == '*' and dow == '*':
        return {"frequency": "DAILY", "time": st, "day": None}
    
    elif dom == '*' and month == '*' and dow != '*':
        # Mapeo de días de la semana (cron: 0=Domingo a 6=Sábado)
        dow_map = {
            '0': 'SUN',
            '1': 'MON',
            '2': 'TUE',
            '3': 'WED',
            '4': 'THU',
            '5': 'FRI',
            '6': 'SAT',
            '7': 'SUN'
        }
        day_str = dow_map.get(dow, 'MON')
        return {"frequency": "WEEKLY", "time": st, "day": day_str}
    
    elif dom != '*' and month == '*' and dow == '*':
        return {"frequency": "MONTHLY", "time": st, "day": dom}
    
    else:
        # Fallback a DAILY si la expresión es demasiado compleja para la UI simple
        return {"frequency": "DAILY", "time": st, "day": None}

def create_or_update_windows_task(job) -> None:
    """
    Crea o actualiza una tarea programada en Windows usando schtasks.
    """
    # Si no tiene cron o no es de tipo cron, asegurarse de que no exista
    if not job.schedule_type or job.schedule_type.lower() != 'cron' or not job.schedule_cron:
        delete_windows_task(job.id)
        return

    task_name = f"SolbaBackups\\Job_{job.id}"
    
    # El comando invoca un webhook local usando PowerShell
    command = f'powershell.exe -WindowStyle Hidden -Command "Invoke-RestMethod -Uri http://localhost:8765/api/v1/jobs/{job.id}/run -Method Post"'

    try:
        parsed = parse_cron_to_schtasks(job.schedule_cron)
        freq = parsed["frequency"]
        time_st = parsed["time"]
        day = parsed["day"]

        # Base schtasks command
        cmd = [
            "schtasks", "/Create", "/F",
            "/TN", task_name,
            "/TR", command,
            "/SC", freq,
            "/ST", time_st
        ]

        # Agregar el día si aplica
        if freq in ("WEEKLY", "MONTHLY") and day:
            cmd.extend(["/D", day])

        log.info(f"Registrando tarea en Windows Scheduler: {' '.join(cmd)}")
        
        # Ejecutar el comando
        process = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        
        if process.returncode != 0:
            log.error(f"Error creando tarea en Windows Scheduler: {process.stderr or process.stdout}")
            raise Exception(f"schtasks falló: {process.stderr or process.stdout}")
            
    except Exception as e:
        log.error(f"Fallo al integrar con schtasks para Job {job.id}: {str(e)}")

def delete_windows_task(job_id: int) -> None:
    """
    Elimina una tarea programada de Windows.
    """
    task_name = f"SolbaBackups\\Job_{job_id}"
    cmd = ["schtasks", "/Delete", "/TN", task_name, "/F"]
    
    try:
        # Intentar borrar, ignorar errores si no existe
        process = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        if process.returncode == 0:
            log.info(f"Tarea {task_name} eliminada del Programador de Tareas de Windows.")
    except Exception as e:
        log.error(f"Error borrando tarea de Windows {task_name}: {str(e)}")
