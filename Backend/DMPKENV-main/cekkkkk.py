import mysql.connector

# --- Konfigurasi Database (Sesuai kode sebelumnya) ---
DB_CONFIG = {
    'host': 'yamanote.proxy.rlwy.net',
    'user': 'root',
    'password': 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu',
    'database': 'railway',
    'port': 59862,
}

def get_latest_data_by_id(table_name):
    conn = None
    try:
        # 1. Buka Koneksi
        print(f"Mengoneksikan ke database untuk cek tabel '{table_name}'...")
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True) # dictionary=True agar outputnya ada nama kolom

        # 2. Query Utama
        # Logic: Urutkan ID dari besar ke kecil (DESC), ambil 1 teratas
        query = f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 1"
        
        cursor.execute(query)
        result = cursor.fetchone()

        # 3. Tampilkan Hasil
        if result:
            print("\n--- DATA TERBARU DITEMUKAN ---")
            print(f"ID        : {result.get('id')}")
            print(f"Timestamp : {result.get('timestamp')}")
            print(f"Data Full : {result}")
        else:
            print(f"\n[INFO] Tabel '{table_name}' masih kosong.")

    except mysql.connector.Error as err:
        print(f"\n[ERROR] Terjadi kesalahan database: {err}")
    except Exception as e:
        print(f"\n[ERROR] Error lain: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()
            print("\nKoneksi ditutup.")

# --- Eksekusi ---
if __name__ == "__main__":
    # Ganti nama tabel sesuai kebutuhan: 
    # 'emotion_track', 'clothing_track', atau 'head_track'
    TARGET_TABLE = 'emotion_track' 
    
    get_latest_data_by_id(TARGET_TABLE)