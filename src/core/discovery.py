"""
src/core/discovery.py — Escáner de Red Local para Auto-descubrimiento.

Este módulo se encarga de escanear los puertos locales estándar de bases de datos
para ofrecer al usuario una lista de motores disponibles sin necesidad de
configurar manualmente los puertos y el host.
"""

import asyncio
import logging
import re

log = logging.getLogger(__name__)

# Quitar pictogramas / símbolos decorativos de nombres mostrados en UI (corporativo)
_EMOJI_AND_SYMBOL_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # Supplemental Symbols and Pictographs, extended
    "\U00002600-\U000027BF"  # Misc symbols / dingbats
    "\U0000FE00-\U0000FE0F"  # Variation selectors
    "\U0000200D"             # ZWJ
    "]+",
    flags=re.UNICODE,
)


def _clean_display_name(text: str) -> str:
    s = _EMOJI_AND_SYMBOL_RE.sub("", text)
    return " ".join(s.split())

# Puertos estándar de los motores de bases de datos soportados
SUPPORTED_ENGINES = {
    "postgresql": {"port": 5432, "name": "PostgreSQL"},
    "mysql": {"port": 3306, "name": "MySQL / MariaDB"},
    "sqlserver": {"port": 1433, "name": "Microsoft SQL Server"},
}

async def check_port(host: str, port: int, engine_id: str, engine_name: str, timeout: float = 0.5) -> dict | None:
    """
    Intenta establecer una conexión TCP asíncrona a un puerto específico.
    Si tiene éxito, devuelve un diccionario con los datos del servicio.
    """
    try:
        # Abrimos conexión asíncrona con timeout
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        
        log.info("Servicio descubierto: %s en %s:%s", engine_name, host, port)
        label = f"{engine_name} detectado en el puerto {port}"
        return {
            "engine": engine_id,
            "host": host,
            "port": port,
            "name": _clean_display_name(label),
        }
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        # El puerto está cerrado o no responde a tiempo
        return None
    except Exception as e:
        log.warning(f"Error inesperado al escanear {host}:{port} - {str(e)}")
        return None

async def scan_local_databases() -> list[dict]:
    """
    Escanea localhost (127.0.0.1) en busca de motores de BD activos.
    Ejecuta las comprobaciones de forma concurrente para minimizar la latencia.
    """
    host = "127.0.0.1"
    tasks = []
    
    log.info(f"Iniciando escaneo de puertos de bases de datos en {host}...")
    
    for engine_id, info in SUPPORTED_ENGINES.items():
        task = asyncio.create_task(
            check_port(host, info["port"], engine_id, info["name"])
        )
        tasks.append(task)
        
    # Esperamos a que todos los escaneos terminen concurrentemente
    results = await asyncio.gather(*tasks)
    
    # Filtramos los nulos (puertos cerrados)
    active_services = [res for res in results if res is not None]
    
    log.info(f"Escaneo finalizado. {len(active_services)} servicios detectados.")
    return active_services
