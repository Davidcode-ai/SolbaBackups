"""
src/api/routers/logs.py — Router de Logs de Ejecuciones.

Proporciona endpoints para consultar los logs detallados de cada ejecución
y hacer streaming en tiempo real de una ejecución en curso via
Server-Sent Events (SSE).

Prefijo del router : /api/v1/logs
Tag OpenAPI        : Logs

Endpoints:
    GET /{run_id}        → Todos los logs de una ejecución (batch, ya terminada).
    GET /{run_id}/stream → Stream SSE de logs de una ejecución en curso.

Formato de un LogEntry:
    - log_id     : ID único del registro de log.
    - run_id     : ID de la ejecución a la que pertenece.
    - timestamp  : Momento exacto del evento.
    - level      : 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'.
    - stage      : Etapa del pipeline ('connect', 'dump', 'compress',
                   'encrypt', 'upload', 'cleanup', 'done').
    - message    : Texto descriptivo del evento.

Notas sobre SSE:
    El endpoint ``/stream`` usa ``StreamingResponse`` de FastAPI con
    ``media_type="text/event-stream"``. El cliente debe manejar reconexión
    automática (el navegador lo hace nativamente con ``EventSource``).
    El stream se cierra automáticamente cuando el run pasa a estado final
    ('success', 'failed', 'warning').
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.core.models import LogEntryRead

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/logs",
    tags=["Logs"],
)


@router.get(
    "/{run_id}",
    response_model=list[LogEntryRead],
    summary="Obtener todos los logs de una ejecución (batch)",
    description=(
        "Para ejecuciones ya terminadas. Para ejecuciones en curso, "
        "usa el endpoint /stream que es más eficiente."
    ),
)
def get_run_logs(
    run_id: int,
    level: str | None = Query(default=None, description="Filtrar por nivel de log"),
    stage: str | None = Query(default=None, description="Filtrar por etapa del pipeline"),
    db: Session = Depends(get_db),
) -> list[LogEntryRead]:
    """
    Devuelve todos los registros de log de una ejecución de forma síncrona.

    Ideal para consultar ejecuciones históricas ya completadas.

    Args:
        run_id: ID de la ejecución de la que se quieren los logs.
        level:  Filtro opcional por nivel de severidad.
        stage:  Filtro opcional por etapa del pipeline de backup.
        db:     Sesión de BD.

    Returns:
        list[LogEntryRead]: Lista de entradas de log, ordenadas por timestamp.

    Raises:
    """
    raise HTTPException(status_code=501, detail="Log stream endpoints are not registered in server lifespan.")


@router.get(
    "/{run_id}/stream",
    summary="Stream SSE de logs en tiempo real",
    description=(
        "Abre un canal Server-Sent Events que emite nuevas entradas de log "
        "a medida que el pipeline de backup las genera. El stream se cierra "
        "automáticamente al terminar la ejecución."
    ),
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Stream de eventos SSE",
        }
    },
)
async def stream_run_logs(
    run_id: int,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Endpoint SSE que emite logs de una ejecución en tiempo real.

    Implementación:
        1. Verifica que el ``run_id`` existe.
        2. Determina el último ``log_id`` ya enviado (empieza en 0).
        3. Entra en un bucle async que consulta la BD cada 500ms buscando
           nuevos logs con ``log_id > last_sent_id``.
        4. Emite cada nuevo log como evento SSE en formato JSON.
        5. Termina el stream cuando el run alcanza un estado final.

    Formato de cada evento SSE emitido:
        ```
        event: log
        data: {"log_id": 42, "level": "INFO", "stage": "dump", "message": "..."}

        event: done
        data: {"status": "success"}
        ```

    Args:
        run_id: ID de la ejecución a monitorizar.
        db:     Sesión de BD (se usa para polling de nuevos logs).

    Returns:
        StreamingResponse: Respuesta de tipo ``text/event-stream``.

    Raises:
        HTTPException 404: Si la ejecución no existe.
    """
    raise HTTPException(status_code=501, detail="Log stream endpoints are not registered in server lifespan.")


async def _log_event_generator(run_id: int, db: Session):
    """
    Generador asíncrono que produce eventos SSE para el stream de logs.

    Se llama desde ``stream_run_logs`` y es el corazón del sistema de
    streaming. Hace polling a la BD SQLite con un intervalo configurable
    para obtener nuevas entradas de log.

    Args:
        run_id: ID de la ejecución a monitorizar.
        db:     Sesión de BD compartida con el endpoint.

    Yields:
        str: Fragmento de texto en formato SSE (``event: ...\ndata: ...\n\n``).
    """
    yield "event: error\ndata: Not implemented\n\n"
