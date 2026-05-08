# 🛡️ SolbaBackups

**SolbaBackups** es un sistema automatizado, resiliente y autogestionado para la creación, encriptación y subida de copias de seguridad de bases de datos y carpetas, diseñado para funcionar tanto en entornos locales como en la nube. 

Desarrollado con una arquitectura moderna que separa el motor de ejecución del dashboard de gestión, garantizando un rendimiento óptimo y una gestión sencilla sin necesidad de tocar una sola línea de código tras la instalación.

---

## ✨ Características Principales

* **☁️ Integración Nube (Google Drive)**: Subida asíncrona de archivos pesados con soporte resumible y tolerancia a fallos.
* **🕰️ Programación Avanzada (APScheduler)**: Ejecución de copias bajo demanda o programadas mediante expresiones Cron o intervalos regulares.
* **🗑️ Garbage Collector (Retención Inteligente)**: Sistema de purga automática que elimina copias antiguas tanto en el disco local como en la nube, basándose en políticas globales o específicas por Job.
* **📧 Alertas Inteligentes (SMTP)**: Notificaciones automáticas por correo electrónico al administrador en caso de que un proceso de backup falle, adjuntando logs detallados.
* **🔒 Seguridad de Origen a Fin**: Compresión `.zip` nativa y capacidad de encriptación modular para proteger la integridad y confidencialidad de los datos.
* **📊 Dashboard Gráfico (Web GUI)**: Panel de control moderno en modo oscuro para crear tareas, ver el historial de ejecuciones y configurar opciones globales, todo en tiempo real (vía SSE).

---

## 🏗️ Arquitectura Técnica

El proyecto está diseñado sobre un stack ligero pero extremadamente robusto:

* **Backend / Core**: 🐍 `Python 3.12+` junto con el framework asíncrono **FastAPI**.
* **Base de Datos Local**: 🗄️ `SQLite` gestionada a través del ORM **SQLAlchemy 2.0**.
* **Frontend**: 🖥️ **Vanilla JavaScript** y HTML5, estilizado de manera impecable con **Tailwind CSS**. 
* **Gestión de Tareas**: ⚙️ `APScheduler` para la automatización en segundo plano de manera nativa sin necesidad de workers externos como Celery.

---

## 🚀 Guía de Instalación Rápida

Sigue estos pasos para desplegar el proyecto en tu entorno local o servidor:

### 1. Clonar el Repositorio
```bash
git clone https://github.com/Davidcode-ai/SolbaBackups.git
cd SolbaBackups
```

### 2. Crear y Activar el Entorno Virtual (Recomendado)
Para evitar conflictos de dependencias, aisla el entorno de la aplicación:

**En Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**En Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar las Dependencias
El proyecto incluye un archivo preparado con todas las librerías necesarias:
```bash
pip install -r requirements.txt
# Opcionalmente, para la versión que incluye entorno web local:
pip install -r requirements_web.txt
```

### 4. Inicializar y Ejecutar
Una vez instaladas las dependencias, inicializa la base de datos (se creará automáticamente `solba_data.db`) y arranca el servidor.

```bash
# Arranca el servidor FastAPI y el Dashboard en el puerto 8000
python solba_web.py
```

Accede al dashboard de gestión abriendo en tu navegador:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🤝 Contribuciones y Equipo
Este proyecto es desarrollado por **Davidcode-ai**. Las contribuciones, sugerencias y reportes de bugs son bienvenidos a través de los Issues y Pull Requests del repositorio.
