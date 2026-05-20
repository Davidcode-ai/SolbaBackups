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
    command = (
        f'powershell.exe -WindowStyle Hidden -Command '
        f'"Invoke-RestMethod -Uri http://localhost:8765/api/v1/jobs/{job.id}/run?trigger=scheduled -Method Post"'
    )

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

        # Si el PC estaba apagado a la hora programada, ejecutar al encender
        _enable_start_when_available(task_name)
            
    except Exception as e:
        log.error(f"Fallo al integrar con schtasks para Job {job.id}: {str(e)}")


def _enable_start_when_available(task_name: str) -> None:
    """
    Activa StartWhenAvailable en la tarea de Windows (ejecutar al encender si se perdió la hora).
    task_name formato: SolbaBackups\\Job_5
    """
    folder, _, name = task_name.rpartition("\\")
    if not folder or not name:
        return
    ps = (
        f"$t = Get-ScheduledTask -TaskPath '\\{folder}\\' -TaskName '{name}' -ErrorAction SilentlyContinue; "
        f"if ($t) {{ $s = $t.Settings; $s.StartWhenAvailable = $true; "
        f"Set-ScheduledTask -TaskPath '\\{folder}\\' -TaskName '{name}' -Settings $s | Out-Null }}"
    )
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except Exception as e:
        log.warning("No se pudo activar StartWhenAvailable en %s: %s", task_name, e)

def get_windows_task_status(job_id: int) -> dict:
    """
    Consulta si la tarea existe en el Programador de Windows y devuelve datos útiles para la UI.
    """
    task_name = f"SolbaBackups\\Job_{job_id}"
    cmd = ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST", "/V"]
    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except Exception as e:
        return {"registered": False, "task_name": task_name, "error": str(e)}

    if process.returncode != 0:
        return {
            "registered": False,
            "task_name": task_name,
            "error": (process.stderr or process.stdout or "").strip() or "Tarea no encontrada",
        }

    parsed: dict[str, str] = {}
    for line in (process.stdout or "").splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            parsed[key.strip()] = val.strip()

    return {
        "registered": True,
        "task_name": task_name,
        "status": parsed.get("Status", parsed.get("Estado")),
        "next_run": parsed.get("Next Run Time", parsed.get("Próxima hora de ejecución programada")),
        "last_run": parsed.get("Last Run Time", parsed.get("Última hora de ejecución")),
        "schedule_type": parsed.get("Schedule Type", parsed.get("Tipo de programación")),
        "start_when_available": parsed.get("Start When Available", parsed.get("Iniciar la tarea cuando esté disponible")),
    }


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
