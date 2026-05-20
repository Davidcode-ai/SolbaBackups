import sqlite3
import os
from src.db.database import resolve_db_path

def migrate():
    db_path = resolve_db_path()
    print(f"Migrando base de datos en: {db_path}")
    
    if not db_path.exists():
        print("La base de datos no existe. Se creará al arrancar la app.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 1. Verificar columnas en la tabla 'jobs'
    cursor.execute("PRAGMA table_info(jobs)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Columnas que sabemos que pueden faltar tras el pull
    missing_jobs_columns = [
        ("dest_gdrive_folder_name", "TEXT"),
    ]

    for col_name, col_type in missing_jobs_columns:
        if col_name not in columns:
            print(f"Añadiendo columna '{col_name}' a la tabla 'jobs'...")
            try:
                cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
                print(f"Columna '{col_name}' añadida con éxito.")
            except Exception as e:
                print(f"Error añadiendo columna '{col_name}': {e}")
        else:
            print(f"La columna '{col_name}' ya existe.")

    conn.commit()
    conn.close()
    print("Migración finalizada.")

if __name__ == "__main__":
    migrate()
