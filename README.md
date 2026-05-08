# SolbaBackups 🗄️

**SolbaBackups** es una solución automatizada, integral y reactiva para la gestión de copias de seguridad de bases de datos. Diseñada para operar sin fricciones, permite centralizar el volcado (dump), compresión, cifrado y transferencia de múltiples motores de bases de datos hacia destinos locales o en la nube (como Google Drive). Todo ello orquestado desde una interfaz web moderna, responsiva y orientada a la experiencia del usuario (UI/UX).

---

## 🚀 Arquitectura y Features

*   **Motor de Orquestación Asíncrono**: Integrado con `APScheduler`, gestiona las tareas en segundo plano dentro del propio Event Loop de FastAPI. Sin bloqueos, de forma concurrente y eficiente.
*   **Interfaz Web UI/UX Reactiva**: Un panel de control *single-page* creado con Vanilla JS y Tailwind CSS (tema oscuro nativo). Proporciona alertas visuales, modales de confirmación, validación reactiva de formularios y *streaming* de logs sin necesidad de recargar.
*   **Almacenamiento Híbrido**: Descarga y comprime tus volcados localmente, o prográmalos para subir automáticamente a **Google Drive** asegurando la redundancia.
*   **Garbage Collector (Política de Retención)**: Define cuántos días mantener tus backups. SolbaBackups se encargará de purgar automáticamente los archivos obsoletos para ahorrar espacio de almacenamiento.
*   **Alertas y Notificaciones**: Soporte para notificaciones por correo (SMTP) para alertar a los administradores en caso de que alguna tarea de backup falle críticamente.

---

## 📂 Estructura del Proyecto

El código está estructurado mediante arquitectura por capas para facilitar su mantenimiento y expansión:

```text
SolbaBackups/
├── solba_web.py                # Punto de entrada de la aplicación (Inicia FastAPI + Uvicorn)
├── .env.example                # Plantilla de variables de entorno
└── src/
    ├── api/                    # Capa de transporte y endpoints REST (Routers)
    │   ├── server.py           # Configuración principal de FastAPI
    │   └── routers/            # Endpoints (Jobs, Historial, Settings)
    ├── core/                   # Lógica de negocio core
    │   ├── job_manager.py      # Orquestador del pipeline (Dump -> Compress -> Upload)
    │   ├── job_scheduler.py    # Enlace con APScheduler
    │   └── models.py           # Modelos de validación (Pydantic)
    ├── db/                     # Capa de persistencia (SQLAlchemy + SQLite)
    │   ├── crud.py             # Operaciones Create, Read, Update, Delete
    │   └── database.py         # Conexión a la base de datos
    ├── frontend/               # Interfaz gráfica de usuario
    │   ├── index.html          # Estructura del panel web
    │   └── assets/             # Estilos y JS (app.js)
    ├── connectors/             # Motores de base de datos soportados (PostgreSQL, MySQL...)
    └── destinations/           # Adaptadores de destino (Local, Google Drive)
```

---

## ⚙️ Configuración Inicial

Antes de arrancar SolbaBackups por primera vez, necesitas definir tus parámetros de entorno.

1. **Renombra el archivo de entorno**:
   Copia el archivo `.env.example` y renómbralo a `.env`.
   
2. **Configura tus variables clave** en `.env`:
   ```env
   # Base de Datos Interna de SolbaBackups
   DATABASE_URL=sqlite:///./solba.db

   # Configuración de Google Drive (Ruta absoluta recomendada)
   GDRIVE_CREDENTIALS_PATH=/ruta/absoluta/a/tus/credentials.json

   # Configuración de Alertas por Email (SMTP)
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=tu_correo@gmail.com
   SMTP_PASSWORD=tu_contraseña_de_aplicacion
   ```

---

## 💻 Uso y Ejecución

SolbaBackups se ejecuta a través de Python y FastAPI. 

1. **Instala las dependencias** (si no lo has hecho ya):
   ```bash
   pip install -r requirements.txt
   ```

2. **Arranca el servidor**:
   Desde la raíz del proyecto, ejecuta el script principal:
   ```bash
   python solba_web.py
   ```

3. **Accede a la Interfaz Web**:
   Abre tu navegador de confianza y dirígete a:
   [http://localhost:8765](http://localhost:8765)

   Desde el panel de control podrás crear tus primeros Jobs, definir la frecuencia (Cron, Diaria, por Intervalos) y ejecutar simulaciones manuales.
