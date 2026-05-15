# ApiWhatsApp Microservice

**ApiWhatsApp** es un microservicio robusto y asíncrono diseñado para gestionar el envío de notificaciones de WhatsApp utilizando la API Oficial de Meta (WhatsApp Cloud API). Implementa el patrón **Transactional Outbox**, apoyándose en una base de datos externa (Supabase PostgreSQL) para encolar los mensajes y enviarlos en un proceso secundario (`worker`), lo que garantiza que nunca se pierdan notificaciones por caídas de red o errores temporales de Meta.

Aunque ha sido empaquetado junto a **SolbaBackups**, está diseñado como un **sistema autónomo e independiente** que puede ser consumido por cualquier otro programa o ERP que necesite enviar WhatsApps transaccionales.

## 🚀 Características Principales

*   **REST API:** Endpoint HTTP simple para encolar notificaciones de forma inmediata (respuesta rápida `202 Accepted`).
*   **Worker en Segundo Plano:** Procesa la cola de envíos de forma independiente a la API principal.
*   **Soporte de Plantillas (Templates):** Total compatibilidad con las plantillas dinámicas de Meta (`hello_world`, `solba_backup_status`, etc.) e inserción de variables.
*   **Gestión de Errores y Reintentos:** Registra detalladamente por qué Meta ha rechazado un mensaje (ej. plantilla no encontrada, error de autenticación).
*   **Asíncrono:** Construido sobre FastAPI y `asyncpg` para un rendimiento máximo.

---

## 🛠️ Instalación y Configuración

### 1. Requisitos
*   Python 3.12+
*   Cuenta de [Meta Developers](https://developers.facebook.com/) con WhatsApp configurado.
*   Cuenta de [Supabase](https://supabase.com/) (o base de datos PostgreSQL) para almacenar la cola de mensajes.

### 2. Entorno Local

```bash
cd ApiWhatsApp
python -m venv venv
# Activar entorno (Windows)
.\venv\Scripts\activate
# Activar entorno (Linux/Mac)
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Variables de Entorno (`.env`)

Crea un archivo `.env` en la raíz de la carpeta `ApiWhatsApp` copiando el ejemplo suministrado (`.env.example`):

```env
# Conexión a la base de datos (Supabase)
DATABASE_URL=postgresql+asyncpg://usuario:password@host:5432/postgres?statement_cache_size=0

# Credenciales de Meta (WhatsApp Business API)
META_ACCESS_TOKEN=tu_token_de_acceso_permanente_o_temporal
WHATSAPP_PHONE_ID=1020834011123459

# Modo debug (true/false)
DEBUG_MODE=true
```

---

## 🏃‍♂️ Arrancar el Microservicio

Para iniciar el servidor web y el worker en segundo plano simultáneamente:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
*La API estará disponible en `http://localhost:8000` y la documentación interactiva en `http://localhost:8000/docs`.*

---

## 📡 Cómo Consumir la API (Desde otros programas)

Cualquier programa puede enviar un WhatsApp haciendo una petición HTTP POST al endpoint `/api/v1/notifications`.

### Endpoint: `POST /api/v1/notifications`

**Payload esperado (JSON):**

```json
{
  "to": "34600000000",
  "template_name": "solba_backup_status",
  "language_code": "es_ES",
  "template_vars": [
    "Backup Base de Datos Principal",
    "Manual",
    "✅ ÉXITO"
  ]
}
```

*   `to`: Número de teléfono en formato internacional (E.164) **sin** el signo `+`.
*   `template_name`: El nombre exacto de la plantilla aprobada en Meta.
*   `language_code`: El código de idioma configurado en Meta (ej. `es_ES` para Español de España, `en_US` para Inglés).
*   `template_vars`: Lista de cadenas de texto (strings). El orden de la lista se mapeará automáticamente a `{{1}}`, `{{2}}`, `{{3}}`, etc. en el cuerpo del mensaje de la plantilla de Meta.

### Ejemplo de Petición con Python (Usando `requests`)

```python
import requests

payload = {
    "to": "34622430735",
    "template_name": "hello_world",
    "language_code": "en_US",
    "template_vars": []
}

response = requests.post("http://localhost:8000/api/v1/notifications", json=payload)

if response.status_code == 202:
    print(f"Notificación encolada con éxito. ID: {response.json()['id']}")
else:
    print("Error al encolar la notificación")
```

---

## 🗃️ Integración con SolbaBackups

En SolbaBackups, la integración ya está resuelta internamente. Solo debes asegurarte de:
1. Tener corriendo este microservicio `ApiWhatsApp` en el puerto 8000.
2. Configurar el archivo `.env` de SolbaBackups con la URL de esta API:
   `WHATSAPP_API_URL=http://localhost:8000`
3. Usar el nombre de la plantilla acordada: `solba_backup_status`.
