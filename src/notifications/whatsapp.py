"""
src/notifications/whatsapp.py — Cliente HTTP REST para ApiWhatsApp Outbox.

SolbaBackups NO envía WhatsApp directamente: delega al microservicio
ApiWhatsApp mediante una petición HTTP POST. El microservicio encola la
petición en Supabase y devuelve HTTP 202 inmediatamente; un worker interno
gestiona el envío real a Meta Cloud API y los reintentos.

Flujo:
    job_runner.py
        └── whatsapp_notifier.send_backup_status(...)
              └── POST {WHATSAPP_API_URL}/api/v1/notifications
                    └── ApiWhatsApp Worker → Meta Cloud API → WhatsApp

Template utilizado: ``solba_backup_status``
Estructura del template en Meta Business:
    "Hola! El sistema Solba ha generado una notificación:
     Evento: {{1}}
     Detalles: {{2}}
     Estado: {{3}}"

Variables dinámicas:
    {{1}}  →  Nombre del Job de backup  (ej: "Backup PostgreSQL Producción")
    {{2}}  →  Tipo de ejecución          (ej: "Manual" | "Programada")
    {{3}}  →  Estado del resultado       (ej: "✅ ÉXITO" | "❌ ERROR")

Configuración (.env de SolbaBackups):
    WHATSAPP_API_URL   → URL base de ApiWhatsApp (default: http://localhost:8000)
    WHATSAPP_PHONE     → Número destino E.164 sin '+' (ej: 34622430735)
    WHATSAPP_ENABLED   → true | false — permite desactivar sin tocar código
    WHATSAPP_TEMPLATE  → Nombre del template (default: solba_backup_status)
    WHATSAPP_LANGUAGE  → Código de idioma del template (default: es_ES)
    WHATSAPP_TIMEOUT   → Timeout HTTP en segundos (default: 5)
"""

import logging
import os
import re

log = logging.getLogger(__name__)

# Expresión para limpiar el número de teléfono: solo dígitos
_PHONE_CLEAN_RE = re.compile(r"[^\d]")


# ──────────────────────────────────────────────────────────────────────────────
# Cliente HTTP REST para ApiWhatsApp
# ──────────────────────────────────────────────────────────────────────────────

class WhatsAppClient:
    """
    Cliente ligero que encola notificaciones en ApiWhatsApp vía HTTP REST.

    Diseñado para ser instanciado una sola vez al inicio de la aplicación
    (singleton en ``whatsapp_notifier``). Lee su configuración del entorno
    en el momento de la primera llamada para respetar el patrón de
    configuración tardía de SolbaBackups.

    Principios de diseño:
        - Nunca lanza excepciones que puedan interrumpir un backup.
        - Usa ``requests`` (ya en requirements_web.txt) o ``urllib`` como
          fallback si ``requests`` no está disponible.
        - Registra en logs toda la trazabilidad: id de notificación,
          destino, template y estado de la respuesta.
    """

    def __init__(self) -> None:
        # Configuración leída en tiempo de instanciación (al arrancar la app)
        # Se puede sobrescribir en tests
        self._reload_config()

    def _reload_config(self) -> None:
        """Lee (o relee) la configuración desde variables de entorno."""
        from dotenv import load_dotenv
        load_dotenv()

        self.enabled       = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
        self.api_url       = os.getenv("WHATSAPP_API_URL", "http://localhost:8000").rstrip("/")
        self.default_phone = _PHONE_CLEAN_RE.sub("", os.getenv("WHATSAPP_PHONE", ""))
        self.template      = os.getenv("WHATSAPP_TEMPLATE", "solba_backup_status")
        self.language      = os.getenv("WHATSAPP_LANGUAGE", "es_ES")
        self.timeout       = int(os.getenv("WHATSAPP_TIMEOUT", "5"))

    # ──────────────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────────────

    def send_backup_status(
        self,
        job_name: str,
        trigger: str,
        success: bool,
        phone: str | None = None,
    ) -> bool:
        """
        Encola una notificación de estado de backup usando el template
        ``solba_backup_status``.

        Mapeo de variables del template:
            {{1}} → job_name   (nombre del job, ej: "Backup PG Producción")
            {{2}} → trigger    (tipo de ejecución, ej: "Manual" | "Programada")
            {{3}} → estado     ("✅ ÉXITO" | "❌ ERROR")

        Args:
            job_name: Nombre del Job de backup.
            trigger:  Origen de la ejecución ('manual' | 'scheduled').
            success:  True si el backup terminó correctamente.
            phone:    Número de destino (E.164 sin '+'). Si se omite, se
                      usa WHATSAPP_PHONE del .env.

        Returns:
            True  → notificación encolada correctamente en ApiWhatsApp.
            False → desactivado, sin configurar, o error de conexión.
        """
        estado = "✅ ÉXITO" if success else "❌ ERROR"
        trigger_label = trigger.capitalize()

        return self._send(
            phone=phone,
            template_vars=[job_name, trigger_label, estado],
        )

    def send(self, message: str, phone: str | None = None) -> bool:
        """
        Compatibilidad con la interfaz anterior (mensaje de texto libre).

        Empaqueta el texto en el campo {{1}} del template, dejando {{2}} y
        {{3}} como cadenas vacías. Úsalo solo para notificaciones genéricas
        que no encajen en ``send_backup_status``.

        Args:
            message: Texto libre del mensaje.
            phone:   Número de destino opcional.
        """
        log.debug(
            "WhatsApp: send() genérico llamado. "
            "Considera usar send_backup_status() para notificaciones de backup."
        )
        return self._send(
            phone=phone,
            template_vars=[message, "", ""],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────────────────────

    def _send(
        self,
        template_vars: list,
        phone: str | None = None,
    ) -> bool:
        """
        Realiza la petición HTTP POST a ApiWhatsApp.

        Implementa el No-Op fallback en todos los casos de error:
        - WHATSAPP_ENABLED=false  → log.debug, retorna False
        - Sin URL o sin teléfono  → log.warning, retorna False
        - Timeout / conexión       → log.error, retorna False (backup continúa)
        - HTTP 4xx / 5xx           → log.error con detalle, retorna False
        """
        if not self.enabled:
            log.debug("WhatsApp desactivado (WHATSAPP_ENABLED=false). Notificación omitida.")
            return False

        target_phone = _PHONE_CLEAN_RE.sub("", phone or self.default_phone)
        if not target_phone:
            log.warning(
                "⚠️  WhatsApp: número de teléfono no configurado. "
                "Define WHATSAPP_PHONE en el .env o pasa el número explícitamente."
            )
            return False

        if not self.api_url:
            log.warning(
                "⚠️  WhatsApp: WHATSAPP_API_URL no configurada. Notificación omitida."
            )
            return False

        endpoint = f"{self.api_url}/api/v1/notifications"
        payload  = {
            "to":            target_phone,
            "template_name": self.template,
            "language_code": self.language,
            "template_vars": template_vars,
        }

        try:
            return self._http_post(endpoint, payload, target_phone)

        except Exception as exc:
            # Captura cualquier error inesperado para proteger el backup
            log.error(
                "❌ WhatsApp: error inesperado al encolar notificación para %s: %s",
                target_phone, exc,
            )
            return False

    def _http_post(self, endpoint: str, payload: dict, target_phone: str) -> bool:
        """
        Ejecuta el POST HTTP. Usa ``requests`` si está disponible;
        cae a ``urllib`` como fallback de stdlib.
        """
        try:
            import requests as req_lib
        except ImportError:
            return self._http_post_urllib(endpoint, payload, target_phone)

        try:
            resp = req_lib.post(
                endpoint,
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code == 202:
                data = resp.json()
                log.info(
                    "📱 Notificación WhatsApp encolada | id=%s | destino=+%s | "
                    "template=%s | estado=PENDING",
                    data.get("id", "?"), target_phone, self.template,
                )
                return True

            log.error(
                "❌ WhatsApp: ApiWhatsApp respondió HTTP %s para +%s. Body: %s",
                resp.status_code, target_phone, resp.text[:200],
            )
            return False

        except req_lib.exceptions.Timeout:
            log.error(
                "❌ WhatsApp: timeout (%ss) conectando a ApiWhatsApp (%s). "
                "El backup continúa.",
                self.timeout, endpoint,
            )
            return False

        except req_lib.exceptions.ConnectionError:
            log.error(
                "❌ WhatsApp: no se pudo conectar a ApiWhatsApp (%s). "
                "¿Está el servicio corriendo? El backup continúa.",
                endpoint,
            )
            return False

    def _http_post_urllib(self, endpoint: str, payload: dict, target_phone: str) -> bool:
        """Fallback HTTP usando solo stdlib (urllib)."""
        import json
        import urllib.request
        import urllib.error

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                if resp.status == 202:
                    body = json.loads(resp.read().decode("utf-8"))
                    log.info(
                        "📱 Notificación WhatsApp encolada | id=%s | destino=+%s | "
                        "template=%s | estado=PENDING",
                        body.get("id", "?"), target_phone, self.template,
                    )
                    return True
                log.error(
                    "❌ WhatsApp: ApiWhatsApp respondió HTTP %s para +%s.",
                    resp.status, target_phone,
                )
                return False

        except urllib.error.URLError as exc:
            log.error(
                "❌ WhatsApp: error de red conectando a ApiWhatsApp (%s): %s. "
                "El backup continúa.",
                endpoint, exc,
            )
            return False

    def health_check(self) -> bool:
        """
        Comprueba que ApiWhatsApp esté disponible y su BD conectada.

        Returns:
            True si el servicio responde ``{"status": "online"}``.
        """
        try:
            import requests as req_lib
            resp = req_lib.get(f"{self.api_url}/health", timeout=self.timeout)
            data = resp.json()
            is_ok = data.get("status") == "online"
            if is_ok:
                log.info(
                    "✅ ApiWhatsApp health check OK | BD=%s | versión=%s",
                    data.get("database", "?"), data.get("version", "?"),
                )
            else:
                log.warning("⚠️  ApiWhatsApp health check reportó estado: %s", data)
            return is_ok
        except Exception as exc:
            log.warning("⚠️  ApiWhatsApp no disponible en %s: %s", self.api_url, exc)
            return False


# ──────────────────────────────────────────────────────────────────────────────
# Instancia global (singleton ligero — misma convención que email notifier)
# ──────────────────────────────────────────────────────────────────────────────
whatsapp_notifier = WhatsAppClient()
