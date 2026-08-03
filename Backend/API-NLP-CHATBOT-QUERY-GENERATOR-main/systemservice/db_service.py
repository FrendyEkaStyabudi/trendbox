# Di dalam file: backend/services/db_service.py

import mysql.connector
import pandas as pd
import re
from config import settings

ALLOWED_TABLES = {"emotion_track", "clothing_track", "head_track"}


def _validate_read_query(sql_query: str):
    """Reject malformed or unsafe model-generated SQL before it reaches MySQL."""
    query = sql_query.strip()
    if not re.match(r"^SELECT\b", query, flags=re.IGNORECASE):
        return "Only SELECT queries are allowed."
    if not re.search(r"\bFROM\b", query, flags=re.IGNORECASE):
        return "The SELECT query is invalid because it has no FROM clause."

    referenced_tables = {
        match.lower().strip("`")
        for match in re.findall(r"\b(?:FROM|JOIN)\s+(`?[A-Za-z_][A-Za-z0-9_]*`?)", query, flags=re.IGNORECASE)
    }
    if not referenced_tables:
        return "The query does not contain a valid source table."
    unsupported = referenced_tables - ALLOWED_TABLES
    if unsupported:
        return f"Disallowed table: {', '.join(sorted(unsupported))}."
    return None

def execute_sql_query(sql_query: str):
    if not sql_query or not sql_query.strip():
        return {"data": None, "error": "An empty SQL query was received."}

    validation_error = _validate_read_query(sql_query)
    if validation_error:
        return {"data": None, "error": validation_error}

    # --- PERBAIKAN DI SINI ---
    db_config = {
        'user': settings.DB_USER,
        'password': settings.DB_PASSWORD,
        'database': settings.DB_NAME,
        'connection_timeout': 10
    }
    if settings.INSTANCE_CONNECTION_NAME:
        db_config['unix_socket'] = f"/cloudsql/{settings.INSTANCE_CONNECTION_NAME}"
    else:
        db_config['host'] = settings.DB_HOST
        db_config['port'] = settings.DB_PORT
    # -------------------------

    conn = None
    cursor = None
    try:
        print(f"DB Service: Mencoba koneksi ke DB {settings.DB_USER}@{settings.DB_HOST}:{settings.DB_PORT}") # Log port
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        print(f"DB Service: Mengeksekusi SQL: {sql_query}")
        cursor.execute(sql_query)
        
        results = [dict(row) for row in cursor.fetchall()]
        print(f"DB Service: Mengambil {len(results)} baris.")
        if results:
            # Konversi kolom datetime ke string agar aman untuk JSON
            df = pd.DataFrame(results)
            for col in df.select_dtypes(include=['datetime64[ns]', 'datetime', 'datetimetz']).columns:
                df[col] = df[col].astype(str)
            return {"data": df.to_dict(orient='records'), "error": None}
        else:
            return {"data": [], "error": None, "info": "No data was found for this query."}

    except mysql.connector.Error as err:
        error_msg = f"MySQL Error: {err}"
        print(f"DB Service {error_msg}")
        return {"data": None, "error": error_msg}
    except Exception as e:
        print(f"DB Service General Error: {e}")
        return {"data": None, "error": f"A database service error occurred: {str(e)}"}
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
