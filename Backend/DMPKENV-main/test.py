import pandas as pd
import mysql.connector
from mysql.connector import Error
import sys

# Load the CSV file
# PASTIKAN NAMA FILE CSV SUDAH BENAR
try:
    df = pd.read_csv('data_september_12_13_14_dari_agustus.csv')
    print("CSV file 'data_september_12_13_14_dari_agustus.csv' loaded successfully.")
except FileNotFoundError:
    print("Error: The file 'data_september_12_13_14_dari_agustus.csv' was not found.")
    sys.exit()

# Hapus kolom 'id' dari DataFrame jika ada, karena database akan mengisinya secara otomatis
if 'id' in df.columns:
    df = df.drop(columns=['id'])
    print("Column 'id' dropped from DataFrame, will use auto-increment from database.")

print(f"Total rows to insert: {len(df)}")
# Database configuration
db_config = {
    'host': 'yamanote.proxy.rlwy.net',
    'user': 'root',
    'password': 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu',
    'database': 'railway',
    'port': '59862',
    'connect_timeout': 450
}

def create_db_connection(config):
    """Create a database connection to the MySQL database."""
    connection = None
    try:
        connection = mysql.connector.connect(**config)
        print("MySQL Database connection successful.")
    except Error as err:
        print(f"Error connecting to MySQL: '{err}'")
    return connection

def create_table_if_not_exists(connection):
    """Create the 'emotion_track' table with an auto-incrementing ID."""
    cursor = connection.cursor()
    # --- PERUBAHAN DI SINI ---
    # Mengubah 'id' menjadi INT AUTO_INCREMENT PRIMARY KEY
    sql_create_table = """
    CREATE TABLE IF NOT EXISTS emotion_track (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(255),
        emotion VARCHAR(50),
        confidence DECIMAL(5, 2),
        timestamp DATETIME
    );
    """
    try:
        cursor.execute(sql_create_table)
        connection.commit()
        print("Table 'emotion_track' created or already exists with auto-increment ID.")
    except Error as err:
        print(f"Error creating table: '{err}'")
    finally:
        cursor.close()

def insert_data_with_progress(connection, dataframe, table_name, chunk_size=1000):
    """Insert data in chunks with a progress bar. (No changes needed here)"""
    cursor = connection.cursor()
    
    # Fungsi ini secara dinamis mengambil kolom dari dataframe yang sudah di-drop 'id'-nya
    columns = ', '.join(dataframe.columns)
    placeholders = ', '.join(['%s'] * len(dataframe.columns))
    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

    total_rows = len(dataframe)
    if total_rows == 0:
        print("No data to insert.")
        return
        
    inserted_rows = 0

    # Mengubah dataframe menjadi list of tuples untuk efisiensi
    data_to_insert = [tuple(row) for row in dataframe.itertuples(index=False)]

    print("Starting data insertion...")
    try:
        for i in range(0, total_rows, chunk_size):
            chunk = data_to_insert[i:i + chunk_size]
            cursor.executemany(sql, chunk)
            connection.commit()

            inserted_rows += len(chunk)
            # Update progress bar
            progress = (inserted_rows / total_rows) * 100
            bar_length = 40
            filled_length = int(bar_length * inserted_rows // total_rows)
            bar = '█' * filled_length + ' ' * (bar_length - filled_length)
            sys.stdout.write(f"\rProgress: [{bar}] {progress:.2f}% ({inserted_rows}/{total_rows})")
            sys.stdout.flush()

        sys.stdout.write('\n')
        print(f"All {total_rows} records inserted successfully.")
    except Error as err:
        print(f"\nError during data insertion: '{err}'")
        connection.rollback()
    finally:
        cursor.close()

if __name__ == "__main__":
    conn = create_db_connection(db_config)

    if conn:
        create_table_if_not_exists(conn)
        table_name = "emotion_track"
        insert_data_with_progress(conn, df, table_name)
        
        print("Closing database connection.")
        conn.close()
