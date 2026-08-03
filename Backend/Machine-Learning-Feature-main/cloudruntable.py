# import mysql.connector

# # Config database Cloud SQL kamu
# config = {
#     'host': '34.128.100.191',
#     'user': 'root',
#     'password': 'admin',
#     'database': 'emotion_trendbox'
# }

# try:
#     conn = mysql.connector.connect(**config)
#     cursor = conn.cursor()

#     # Ganti 'emotion_track' dengan nama tabel yang mau kamu cek
#     table_name = 'emotion_track'
#     cursor.execute(f"DESCRIBE {table_name};")

#     columns = cursor.fetchall()

#     print(f"Columns in table '{table_name}':")
#     for col in columns:
#         print(f"Column: {col[0]} | Type: {col[1]} | Null: {col[2]} | Key: {col[3]} | Default: {col[4]} | Extra: {col[5]}")

#     cursor.close()
#     conn.close()

# except mysql.connector.Error as err:
#     print("Connection error:", err)

import mysql.connector
import os

# --- 1. Konfigurasi Database dari Environment Variables ---
# Pastikan Anda sudah mengatur DB_PASSWORD di terminal Anda
# Contoh: set DB_PASSWORD=password_anda
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'yamanote.proxy.rlwy.net'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu'),
    'database': os.getenv('DB_DATABASE', 'railway'),
    'port': int(os.getenv('DB_PORT', 59862)),
}

# Cek apakah password sudah di-set
if not DB_CONFIG['password']:
    print("Error: Environment variable DB_PASSWORD belum di-set.")
    exit()

# Variabel untuk koneksi dan cursor
connection = None
cursor = None

try:
    # --- 2. Membuat Koneksi ke Database ---
    print("Menghubungkan ke database MySQL...")
    connection = mysql.connector.connect(**DB_CONFIG)
    print("Koneksi berhasil!")
    
    # Membuat cursor, dictionary=True agar hasil query bisa diakses seperti dictionary
    cursor = connection.cursor(dictionary=True)
    
    # --- 3. Membuat dan Menjalankan Query SQL ---
    # Query untuk mengambil 20 data terbaru
    query = """
        SELECT timestamp, user_id, emotion, confidence 
        FROM emotion_track 
        ORDER BY timestamp DESC 
        LIMIT 20
    """
    
    print("\nMengambil 20 data terbaru...")
    cursor.execute(query)
    
    # Mengambil semua hasil dari query
    records = cursor.fetchall()
    
    # --- 4. Menampilkan Hasil ---
    if records:
        print(f"Berhasil mendapatkan {len(records)} data:\n")
        # Mencetak header
        print(f"{'Timestamp':<25} {'User ID':<10} {'Emotion':<12} {'Confidence'}")
        print("-" * 65)
        
        for row in records:
            # Format timestamp agar lebih mudah dibaca
            timestamp_formatted = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"{timestamp_formatted:<25} {row['user_id']:<10} {row['emotion']:<12} {row['confidence']}")
    else:
        print("Tidak ada data yang ditemukan di tabel emotion_track.")

except mysql.connector.Error as err:
    print(f"Terjadi error saat terhubung atau mengambil data: {err}")

finally:
    # --- 5. Menutup Koneksi ---
    # Pastikan koneksi dan cursor selalu ditutup untuk melepas resource
    if cursor:
        cursor.close()
    if connection and connection.is_connected():
        connection.close()
        print("\nKoneksi ke database sudah ditutup.")
