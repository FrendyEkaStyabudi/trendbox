import mysql.connector
import os

# --- Konfigurasi Database ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'yamanote.proxy.rlwy.net'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu'), # Sebaiknya gunakan environment variable
    'database': os.getenv('DB_DATABASE', 'railway'),
    'port': int(os.getenv('DB_PORT', 59862)),
}

def delete_target_table():
    connection = None
    try:
        # 1. Membuat koneksi
        connection = mysql.connector.connect(**DB_CONFIG)
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # 2. Perintah SQL untuk menghapus tabel
            # 'IF EXISTS' mencegah error jika tabel sudah tidak ada
            table_name = "attribute_track"
            sql_query = f"DROP TABLE IF EXISTS {table_name}"
            
            print(f"Sedang mencoba menghapus tabel '{table_name}'...")
            
            # 3. Eksekusi perintah
            cursor.execute(sql_query)
            
            # Commit perubahan (penting untuk DDL di beberapa konfigurasi, meski biasanya auto-commit)
            connection.commit()
            
            print(f"BERHASIL: Tabel '{table_name}' telah dihapus (atau memang tidak ditemukan).")

    except mysql.connector.Error as error:
        print(f"GAGAL: Terjadi error saat menghapus tabel: {error}")

    finally:
        # 4. Menutup koneksi
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("Koneksi MySQL ditutup.")

if __name__ == "__main__":
    delete_target_table()