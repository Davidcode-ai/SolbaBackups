"""
crear_db_test.py — Script de utilidad para crear la BD de prueba en MySQL/XAMPP.

Uso:
    python crear_db_test.py

Requisito previo:
    pip install pymysql
"""

import sys

# ── Configuración de conexión ─────────────────────────────────────────────────
HOST     = "127.0.0.1"
PORT     = 3306
USER     = "root"
PASSWORD = ""          # XAMPP usa root sin contraseña por defecto
DB_NAME  = "solba_test_db"
# ─────────────────────────────────────────────────────────────────────────────

def main():
    try:
        import pymysql
    except ImportError:
        print("❌ La librería 'pymysql' no está instalada.")
        print("   Ejecuta: pip install pymysql")
        sys.exit(1)

    print(f"🔌 Conectando a MySQL en {HOST}:{PORT} como '{USER}'...")

    try:
        conn = pymysql.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=PASSWORD,
            charset="utf8mb4",
            connect_timeout=5,
        )
    except pymysql.err.OperationalError as e:
        print(f"❌ No se pudo conectar a MySQL: {e}")
        print("   Asegúrate de que el servicio MySQL de XAMPP está arrancado (verde).")
        sys.exit(1)

    try:
        with conn.cursor() as cursor:
            sql = f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            cursor.execute(sql)
            conn.commit()
            print(f"✅ Base de datos '{DB_NAME}' creada correctamente (o ya existía).")

            # Verificar que existe
            cursor.execute("SHOW DATABASES LIKE %s;", (DB_NAME,))
            result = cursor.fetchone()
            if result:
                print(f"   ✔  Verificada: '{DB_NAME}' está disponible en el servidor.")
            
    except pymysql.err.ProgrammingError as e:
        print(f"❌ Error ejecutando SQL: {e}")
        sys.exit(1)
    finally:
        conn.close()
        print("🔒 Conexión cerrada.")

    print()
    print("─" * 55)
    print("  Ahora puedes usar estos datos en SolbaBackups:")
    print(f"    Host:     {HOST}")
    print(f"    Puerto:   {PORT}")
    print(f"    Usuario:  {USER}")
    print(f"    BD Name:  {DB_NAME}")
    print(f"    Password: (vacía)")
    print("─" * 55)


if __name__ == "__main__":
    main()
