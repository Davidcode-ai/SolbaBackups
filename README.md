<div align="center">
  <img src="src/frontend/assets/logo_solba.png" alt="SolbaBackups Logo" width="250" />
</div>

# 🛡️ SolbaBackups

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)

## 📑 Índice

- [Descripción](#descripcion)
- [Características Principales](#caracteristicas-principales)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Stack Tecnológico](#stack-tecnologico)
- [Arquitectura de Microservicios](#arquitectura-de-microservicios)
- [Guía de Instalación](#guia-de-instalacion)
- [Guía de Configuración](#guia-de-configuracion)
- [Seguridad](#seguridad)
- [Uso Rápido](#uso-rapido)
- [Contribución](#contribucion)
- [Capturas de Pantalla](#capturas-de-pantalla)
- [Equipo de Desarrollo](#equipo-de-desarrollo)
- [Licencia](#licencia)

---

<a id="descripcion"></a>
## 📖 Descripción

**SolbaBackups** es una solución integral y profesional de copias de seguridad diseñada para entornos corporativos. Cuenta con una interfaz web moderna e intuitiva y está diseñada para ejecutarse de forma totalmente invisible en segundo plano como un **Servicio de Windows**. Garantiza la protección continua de los datos críticos de su empresa sin interrumpir el flujo de trabajo del usuario final.

<a id="caracteristicas-principales"></a>
## ✨ Características Principales

* **💾 Motor de Backups Multi-Destino:** Soporte completo para copias de bases de datos PostgreSQL y archivos locales, con capacidad de almacenamiento tanto en discos locales como en la nube (Google Drive).
* **🧠 Retención Inteligente:** Sistema automatizado para la gestión del espacio, eliminando copias antiguas según las políticas de retención configuradas para evitar la saturación del almacenamiento.
* **🔔 Notificaciones Proactivas:** Alertas automáticas en tiempo real sobre el estado de las copias de seguridad enviadas directamente a través de **Correo Electrónico** y **WhatsApp**, manteniendo a los administradores siempre informados.

---

<a id="estructura-del-proyecto"></a>
## 📁 Estructura del Proyecto

```text
SolbaV2/
├── src/
│   ├── api/
│   │   └── routers/                  # Endpoints FastAPI (jobs, history, settings, utils, auth)
│   ├── connectors/                   # Conectores de BD (PostgreSQL, MySQL, SQLServer, SQLite)
│   ├── core/
│   │   ├── job_manager.py            # Orquestador del pipeline de backup
│   │   ├── job_scheduler.py          # Gestión de programación con APScheduler
│   │   ├── cleaner.py                # Garbage Collector (retención de backups)
│   │   └── models.py                 # Modelos Pydantic de la API
│   ├── db/
│   │   ├── models.py                 # Modelos SQLAlchemy (Job, RunHistory, LogEntry)
│   │   ├── crud.py                   # Operaciones CRUD sobre la BD
│   │   └── database.py               # Configuración de sesión SQLAlchemy
│   ├── destinations/                 # Destinos (local, Google Drive)
│   ├── notifications/                # Notificadores (email SMTP, WhatsApp)
│   ├── processors/                   # Compresor ZIP, Encriptador AES
│   └── frontend/
│       ├── index.html                # Dashboard web principal
│       └── assets/
│           ├── js/app.js             # Lógica JS completa (i18n, API, UI)
│           └── css/                  # Estilos CSS
├── tests/
│   ├── conftest.py                   # Fixtures compartidos (BD de test aislada)
│   ├── test_api_routers.py           # Tests de endpoints HTTP
│   ├── test_crud.py                  # Tests de operaciones de BD
│   ├── test_connectors.py            # Tests de conectores (mocks)
│   ├── test_scheduler_and_cleaner.py # Tests de programación y limpieza
│   └── test_integrations.py          # Tests de Google Drive y WhatsApp
├── requirements.txt                  # Dependencias generales del backend
├── requirements_web.txt              # Dependencias específicas de la web
├── solba_web.py                      # Punto de entrada principal
└── .env.example                      # Plantilla de variables de entorno
```

---

<a id="stack-tecnologico"></a>
## 🛠️ Stack Tecnológico

| Capa | Tecnología | Versión |
|---|---|---|
| Backend | FastAPI | 0.111+ |
| ORM | SQLAlchemy | 2.0 |
| BD Interna | SQLite | 3 |
| Scheduler | APScheduler | 3.x |
| Nube | Google Drive API v3 | — |
| Email | smtplib (stdlib) | — |
| WhatsApp | WhatsApp Business HTTP API | — |
| Frontend | Vanilla JS + HTML5 | — |
| Estilos | Tailwind CSS (CDN) | 3.x |
| Iconos | Font Awesome | 6.x |
| Empaquetado | PyInstaller | 6.x |
| Tests | pytest + pytest-cov | 8.x |

---

<a id="arquitectura-de-microservicios"></a>
## 🏗️ Arquitectura de Microservicios

Para asegurar una alta disponibilidad y escalabilidad, el ecosistema de SolbaBackups adopta un enfoque de microservicios:

* **API de Notificaciones (WhatsApp):** El motor de envíos de WhatsApp se ha desacoplado de la aplicación principal. Opera de forma independiente como una API alojada en **Render**, respaldada por una base de datos en **Supabase** para la gestión ágil y centralizada de las comunicaciones.

---

<a id="guia-de-instalacion"></a>
## 🚀 Guía de Instalación

1.  **Descargar:** Obtenga el instalador `.exe` de la última versión estable.
2.  **Instalar:** Ejecute el instalador con privilegios de Administrador. El sistema instalará los binarios y configurará automáticamente el Servicio de Windows.
3.  **Acceder:** Una vez finalizada la instalación, acceda al panel de control en:
    ```bash
    http://localhost:8765
    
```

<a id="guia-de-configuracion"></a>
## ⚙️ Guía de Configuración

* **Google Drive:** Inicie sesión desde el panel utilizando el flujo de OAuth para enlazar su cuenta en la nube de forma segura.
* **Notificaciones:** Configure los parámetros SMTP y los números de destino de WhatsApp desde el menú de configuración para activar las alertas.

---

<a id="seguridad"></a>
## 🔐 Seguridad

- Las contraseñas de BD **nunca se sobreescriben** si se envía un campo vacío en la actualización.
- Las credenciales se almacenan **encriptadas** en la BD SQLite local.
- La API dispone de autenticación básica configurable.

---

<a id="uso-rapido"></a>
## ⚡ Uso rápido (Línea de Comandos)

```bash
solba_web.exe start   # Inicia el servicio
solba_web.exe status  # Verifica el estado del servicio
solba_web.exe stop    # Detiene el servicio
```
<a id="capturas-de-pantalla"></a>
## 📸 Capturas de Pantalla

> El panel de control cuenta con modo oscuro nativo e historial en tiempo real.

### Interfaz Principal (Modo Oscuro)
<img width="100%" alt="Modo oscuro" src="https://github.com/user-attachments/assets/b9c13bef-89dc-4084-bfb6-f678693c9f34" />

### Interfaz Principal (Modo Claro)
<img width="100%" alt="Modo claro" src="https://github.com/user-attachments/assets/4aa47246-13c2-4a5f-a21f-11131fef9e6d" />

---

<a id="equipo-de-desarrollo"></a>
## 👥 Equipo de Desarrollo

| Rol | Nombre |
|---|---|
| 🏗️ Arquitectura & Backend | David |
| 🎨 Frontend & UX | Alejandro |
| 🔌 Conectores & Integraciones | Manuel |
| 🧪 QA & Testing | Equipo Solba |

---

<a id="licencia"></a>
## 📄 Licencia

Distribuido bajo licencia **MIT**. Consulta el archivo `LICENSE` para más detalles.

---

<div align="center">
  *SolbaBackups — Protegiendo sus datos, automatizando su tranquilidad.*
</div>
