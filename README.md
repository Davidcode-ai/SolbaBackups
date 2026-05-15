# 🛡️ SolbaBackups

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)

## 📖 Descripción

**SolbaBackups** es una solución integral y profesional de copias de seguridad diseñada para entornos corporativos. Cuenta con una interfaz web moderna e intuitiva y está diseñada para ejecutarse de forma totalmente invisible en segundo plano como un **Servicio de Windows**. Garantiza la protección continua de los datos críticos de su empresa sin interrumpir el flujo de trabajo del usuario final.

## ✨ Características Principales

*   **💾 Motor de Backups Multi-Destino:** Soporte completo para copias de bases de datos PostgreSQL y archivos locales, con capacidad de almacenamiento tanto en discos locales como en la nube (Google Drive).
*   **🧠 Retención Inteligente:** Sistema automatizado para la gestión del espacio, eliminando copias antiguas según las políticas de retención configuradas para evitar la saturación del almacenamiento.
*   **🔔 Notificaciones Proactivas:** Alertas automáticas en tiempo real sobre el estado de las copias de seguridad enviadas directamente a través de **Correo Electrónico** y **WhatsApp**, manteniendo a los administradores siempre informados.

## 🛠️ Stack Tecnológico

El proyecto está construido sobre tecnologías modernas y robustas para garantizar el máximo rendimiento y fiabilidad:

*   **Lenguaje Base:** Python
*   **Backend & Servidor Web:** FastAPI impulsado por Uvicorn
*   **Empaquetado y Distribución:** PyInstaller (para generar el binario) e Inno Setup (para la creación del instalador profesional en Windows)
*   **Integraciones Cloud:** API nativa de Google Drive

## 🏗️ Arquitectura de Microservicios

Para asegurar una alta disponibilidad y escalabilidad, el ecosistema de SolbaBackups adopta un enfoque de microservicios:

*   **API de Notificaciones (WhatsApp):** El motor de envíos de WhatsApp se ha desacoplado de la aplicación principal. Opera de forma independiente como una API alojada en **Render**, respaldada por una base de datos en **Supabase** para la gestión ágil y centralizada de las comunicaciones.

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

*   **Credenciales y Nube:** Diríjase a la sección de **Configuración** en la interfaz web.
*   **Google Drive:** Inicie sesión directamente desde el panel utilizando el flujo de OAuth para autorizar la aplicación y enlazar su cuenta en la nube de forma segura.
*   **Notificaciones:** Configure los parámetros SMTP (correo emisor, contraseñas de aplicación) y los números de destino de WhatsApp desde el mismo menú para activar las alertas instantáneas.

## 👥 Autores

Desarrollado con dedicación por el equipo de ingeniería:

*   **David**
*   **Manuel**
*   **[Nombre del Tercer Integrante]** 

---
*SolbaBackups — Protegiendo sus datos, automatizando su tranquilidad.*
