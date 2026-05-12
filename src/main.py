"""
Punto de entrada principal de SolbaBackups.

Uso:
    python -m src.main [COMANDO] [OPCIONES]

Comandos disponibles:
    backup    Ejecutar una copia de seguridad
    restore   Restaurar una copia de seguridad
    schedule  Gestionar tareas programadas
    detect    Detectar bases de datos en una máquina
    sync      Sincronizar carpetas
    upload    Subir copia a Google Drive
"""

import sys
import os

# Asegurar que el directorio raíz del proyecto esté en el sys.path
# para evitar ModuleNotFoundError cuando se ejecuta 'python src/main.py'
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.ui.cli import main_cli

if __name__ == "__main__":
    sys.exit(main_cli())

