# 🛡️ SolbaBackups

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)

## 📑 Índice

- [Descripción](#descripción)
- [Características Principales](#características-principales)
- [Stack Tecnológico](#stack-tecnológico)
- [Arquitectura de Microservicios](#arquitectura-de-microservicios)
- [Guía de Instalación](#guía-de-instalación)
- [Guía de Configuración](#guía-de-configuración)
- [Seguridad](#seguridad)
- [Capturas de Pantalla](#capturas-de-pantalla)
- [Equipo de Desarrollo](#equipo-de-desarrollo)
- [Licencia](#licencia)

## 📖 Descripción

**SolbaBackups** es una solución integral y profesional de copias de seguridad diseñada para entornos corporativos. Cuenta con una interfaz web moderna e intuitiva y está diseñada para ejecutarse de forma totalmente invisible en segundo plano como un **Servicio de Windows**. Garantiza la protección continua de los datos críticos de su empresa sin interrumpir el flujo de trabajo del usuario final.

## ✨ Características Principales

* **💾 Motor de Backups Multi-Destino:** Soporte completo para copias de bases de datos PostgreSQL y archivos locales, con capacidad de almacenamiento tanto en discos locales como en la nube (Google Drive).
* **🧠 Retención Inteligente:** Sistema automatizado para la gestión del espacio, eliminando copias antiguas según las políticas de retención configuradas para evitar la saturación del almacenamiento.
* **🔔 Notificaciones Proactivas:** Alertas automáticas en tiempo real sobre el estado de las copias de seguridad enviadas directamente a través de **Correo Electrónico** y **WhatsApp**, manteniendo a los administradores siempre informados.

```bash
pip install pytest pytest-asyncio pytest-mock pytest-cov httpx
python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## 📁 Estructura del Proyecto

```text
SolbaV2/
├── src/
│   ├── api/
│   │   └── routers/          # Endpoints FastAPI (jobs, history, settings, utils, auth)
│   ├── connectors/           # Conectores de BD (PostgreSQL, MySQL, SQLServer, SQLite)
│   ├── core/
│   │   ├── job_manager.py    # Orquestador del pipeline de backup
│   │   ├── job_scheduler.py  # Gestión de programación con APScheduler
│   │   ├── cleaner.py        # Garbage Collector (retención de backups)
│   │   └── models.py         # Modelos Pydantic de la API
│   ├── db/
│   │   ├── models.py         # Modelos SQLAlchemy (Job, RunHistory, LogEntry)
│   │   ├── crud.py           # Operaciones CRUD sobre la BD
│   │   └── database.py       # Configuración de sesión SQLAlchemy
│   ├── destinations/         # Destinos (local, Google Drive)
│   ├── notifications/        # Notificadores (email SMTP, WhatsApp)
│   ├── processors/           # Compresor ZIP, Encriptador AES
│   └── frontend/
│       ├── index.html        # Dashboard web principal
│       └── assets/
│           ├── js/app.js     # Lógica JS completa (i18n, API, UI)
│           └── css/          # Estilos CSS
├── tests/
│   ├── conftest.py           # Fixtures compartidos (BD de test aislada)
│   ├── test_api_routers.py   # Tests de endpoints HTTP
│   ├── test_crud.py          # Tests de operaciones de BD
│   ├── test_connectors.py    # Tests de conectores (mocks)
│   ├── test_scheduler_and_cleaner.py
│   └── test_integrations.py  # Tests de Google Drive y WhatsApp
├── requirements.txt
├── requirements_web.txt
├── solba_web.py              # Punto de entrada principal
└── .env.example
```

## 🛠️ Stack Tecnológico

El proyecto está construido sobre tecnologías modernas y robustas para garantizar el máximo rendimiento y fiabilidad:

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

## 🏗️ Arquitectura de Microservicios

Para asegurar una alta disponibilidad y escalabilidad, el ecosistema de SolbaBackups adopta un enfoque de microservicios:

* **API de Notificaciones (WhatsApp):** El motor de envíos de WhatsApp se ha desacoplado de la aplicación principal. Opera de forma independiente como una API alojada en **Render**, respaldada por una base de datos en **Supabase** para la gestión ágil y centralizada de las comunicaciones.

## 🚀 Guía de Instalación

La implementación de SolbaBackups ha sido diseñada para ser un proceso *plug-and-play* para el cliente final:

1.  **Descargar:** Obtenga el instalador `.exe` de la última versión estable.
2.  **Instalar:** Ejecute el instalador con privilegios de Administrador y siga el asistente interactivo. El sistema instalará los binarios y configurará automáticamente el Servicio de Windows para que se inicie con el sistema.
3.  **Acceder:** Una vez finalizada la instalación, el servicio comenzará a ejecutarse en segundo plano. Puede acceder al panel de control abriendo su navegador web en la siguiente dirección:
    ```bash
    http://localhost:8765
    ```

## ⚙️ Guía de Configuración

Toda la gestión del sistema se realiza de forma centralizada y amigable desde el panel de control web:

* **Credenciales y Nube:** Diríjase a la sección de **Configuración** en la interfaz web.
* **Google Drive:** Inicie sesión directamente desde el panel utilizando el flujo de OAuth para autorizar la aplicación y enlazar su cuenta en la nube de forma segura.
* **Notificaciones:** Configure los parámetros SMTP (correo emisor, contraseñas de aplicación) y los números de destino de WhatsApp desde el mismo menú para activar las alertas instantáneas.

## 🔐 Seguridad

- Las contraseñas de BD **nunca se sobreescriben** si se envía un campo vacío en la actualización de un Job.
- Las credenciales se almacenan encriptadas en la BD SQLite local (no en texto plano en ficheros de configuración).
- La API dispone de autenticación básica configurable a través de los ajustes globales.

## 📸 Capturas de Pantalla

> El panel de control cuenta con modo oscuro nativo, explorador de archivos integrado, historial en tiempo real y un terminal de logs embebido.

### Modo oscuro
<img width="1920" height="926" alt="Modo oscuro" src="https://github.com/user-attachments/assets/b9c13bef-89dc-4084-bfb6-f678693c9f34" />

### Modo claro
<img width="1920" height="917" alt="Modo claro" src="https://github.com/user-attachments/assets/4aa47246-13c2-4a5f-a21f-11131fef9e6d" />

## 🤝 Equipo de Desarrollo

Este proyecto ha sido desarrollado como proyecto de prácticas empresariales:

| Rol | Nombre |
|---|---|
| 🏗️ Arquitectura & Backend | David |
| 🎨 Frontend & UX | Alejandro |
| 🔌 Conectores & Integraciones | Manuel |
| 🧪 QA & Testing | Todos |

> Proyecto desarrollado con metodología ágil e integración continua. Suite de tests automatizados garantizan la estabilidad de cada entrega.

## 📄 Licencia

Distribuido bajo licencia **MIT**. Consulta el archivo `LICENSE` para más detalles.

---

<div align="center">
  *SolbaBackups — Protegiendo sus datos, automatizando su tranquilidad.*<br><br>
  <sub>Hecho con ❤️ y mucho café ☕ por el equipo de prácticas de SolbaBackups</sub>
</div>
