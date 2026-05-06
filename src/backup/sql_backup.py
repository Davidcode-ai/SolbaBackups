"""SQL backup provider module for MySQL and SQL Server."""

from pathlib import Path
from typing import Any

from .base import BaseBackup


class SQLBackup(BaseBackup):
    """Backup provider for MySQL and SQL Server databases."""

    def _do_backup(self, timestamp: str, **kwargs: Any) -> Path:
        """Performs a backup of a MySQL or SQL Server database.

        Args:
            timestamp: The current timestamp string to use in filenames.
            **kwargs: Must contain 'db_type' ('mysql' or 'sqlserver') and
                connection parameters.

        Returns:
            The path to the created backup file.

        Raises:
            ValueError: If db_type is unsupported or parameters are missing.
        """
        db_type = kwargs.get("db_type")
        if db_type == "mysql":
            return self._backup_mysql(timestamp, **kwargs)
        elif db_type == "sqlserver":
            return self._backup_sqlserver(timestamp, **kwargs)
        else:
            raise ValueError(f"Unsupported db_type for SQLBackup: {db_type}")

    def _backup_mysql(self, timestamp: str, **kwargs: Any) -> Path:
        """Performs a MySQL backup using pymysql to extract table schemas and data."""
        import pymysql

        dbname = kwargs.get("dbname")
        if not dbname:
            raise ValueError("dbname is required for MySQL backup.")

        user = kwargs.get("user", "root")
        password = kwargs.get("password", "")
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", 3306)

        dest_filename = f"{dbname}_{timestamp}.sql"
        dest_path = self.dest_dir / dest_filename

        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=dbname,
            port=int(port),
        )

        try:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()

                with open(dest_path, "w", encoding="utf-8") as file_out:
                    file_out.write(f"-- Backup of database: {dbname}\n\n")
                    for (table_name,) in tables:
                        cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                        create_stmt = cursor.fetchone()[1]
                        file_out.write(f"DROP TABLE IF EXISTS `{table_name}`;\n")
                        file_out.write(f"{create_stmt};\n\n")

                        cursor.execute(f"SELECT * FROM `{table_name}`")
                        rows = cursor.fetchall()
                        if rows:
                            for row in rows:
                                values = ", ".join(
                                    repr(str(val)) if val is not None else "NULL"
                                    for val in row
                                )
                                insert_query = (
                                    f"INSERT INTO `{table_name}` VALUES ({values});\n"
                                )
                                file_out.write(insert_query)
                        file_out.write("\n")
        finally:
            conn.close()

        return dest_path

    def _backup_sqlserver(self, timestamp: str, **kwargs: Any) -> Path:
        """Performs a SQL Server backup using pyodbc to run BACKUP DATABASE."""
        import pyodbc

        dbname = kwargs.get("dbname")
        if not dbname:
            raise ValueError("dbname is required for SQL Server backup.")

        server = kwargs.get("server", "localhost")
        user = kwargs.get("user", "")
        password = kwargs.get("password", "")
        driver = kwargs.get("driver", "{ODBC Driver 17 for SQL Server}")

        dest_filename = f"{dbname}_{timestamp}.bak"
        dest_path = self.dest_dir / dest_filename

        conn_str = f"DRIVER={driver};SERVER={server};DATABASE=master;"
        if user and password:
            conn_str += f"UID={user};PWD={password};"
        else:
            conn_str += "Trusted_Connection=yes;"

        with pyodbc.connect(conn_str, autocommit=True) as conn:
            cursor = conn.cursor()
            backup_query = (
                f"BACKUP DATABASE [{dbname}] TO DISK = '{dest_path}' WITH FORMAT"
            )
            cursor.execute(backup_query)
            while cursor.nextset():
                pass

        return dest_path
