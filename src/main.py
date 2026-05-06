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
from src.ui.cli import main_cli

if __name__ == "__main__":
    sys.exit(main_cli())
