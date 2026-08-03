import mysql.connector
import os

# --- Konfigurasi Database ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'yamanote.proxy.rlwy.net'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu'),
    'database': os.getenv('DB_DATABASE', 'railway'),
    'port': int(os.getenv('DB_PORT', 59862)),
    'connect_timeout': 60
}

# --- Konfigurasi Whitelist (Bahasa Inggris) ---

ALLOWED_HEAD = ['hat', 'hair', 'hijab'] 

def process_database():
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print(f"✅ Terhubung ke database: {DB_CONFIG['database']}")
        print("-" * 50)

        # =========================================================
        # LANGKAH 1: Translate Bahasa Indonesia -> Inggris (Khusus Head Track)
        # =========================================================
        print("🌍 [head_track] Menerjemahkan data ke Bahasa Inggris...")
        
        # Mapping perubahan: 'Lama' -> 'Baru'
        translations = {
            'topi': 'hat',
            'rambut': 'hair',
            # 'hijab': 'hijab' # Tidak perlu diubah jika sama
        }
        
        # Asumsi nama kolom adalah 'label', ubah jika perlu
        head_col = 'label' 

        for indo, eng in translations.items():
            query_update = f"UPDATE head_track SET {head_col} = %s WHERE {head_col} = %s"
            cursor.execute(query_update, (eng, indo))
            if cursor.rowcount > 0:
                print(f"   🔄 Mengubah '{indo}' menjadi '{eng}': {cursor.rowcount} data.")

        # =========================================================
        # LANGKAH 2: Hapus Data Sampah (Cleaning)
        # =========================================================
        print("\n🧹 Memulai pembersihan data (Delete invalid rows)...")

        # 3. HEAD TRACK (Sekarang filter pakai bahasa Inggris)
        head_str = ", ".join([f"'{x}'" for x in ALLOWED_HEAD])
        cursor.execute(f"DELETE FROM head_track WHERE {head_col} NOT IN ({head_str})")
        print(f"   👉 [head_track]    Dihapus: {cursor.rowcount} baris (selain {ALLOWED_HEAD})")

        # =========================================================
        # Commit
        conn.commit()
        print("-" * 50)
        print("🎉 Selesai! Data telah diterjemahkan ke Inggris dan dibersihkan.")

    except mysql.connector.Error as err:
        print(f"\n❌ Error Database: {err}")
        if conn:
            conn.rollback()
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    process_database()