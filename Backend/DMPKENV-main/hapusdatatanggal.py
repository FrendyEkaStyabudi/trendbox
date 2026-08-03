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

# --- Daftar Tanggal yang Ingin DIHAPUS ---
# Format: YYYY-MM-DD
TARGET_DATES = [
    '2025-12-04',  # Hari ini
    '2025-12-08',  # 8 Desember
    '2025-12-09'   # 9 Desember
]

# --- Daftar Tabel Target ---
TARGET_TABLES = ['head_track', 'clothing_track', 'emotion_track']

def delete_data_by_dates():
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print(f"✅ Terhubung ke database: {DB_CONFIG['database']}")
        print(f"📅 Target Tanggal Hapus: {TARGET_DATES}")
        print("-" * 50)

        # Siapkan format string untuk query SQL: '2025-12-04', '2025-12-08', ...
        dates_formatted = ", ".join([f"'{d}'" for d in TARGET_DATES])

        total_deleted_all = 0

        for table in TARGET_TABLES:
            # Query Delete: Menghapus jika bagian TANGGAL dari timestamp cocok
            query = f"DELETE FROM {table} WHERE DATE(timestamp) IN ({dates_formatted})"
            
            print(f"🚀 Memproses tabel '{table}'...")
            cursor.execute(query)
            
            rows_deleted = cursor.rowcount
            total_deleted_all += rows_deleted
            print(f"   👉 Berhasil menghapus {rows_deleted} baris data.")

        # Commit perubahan
        conn.commit()
        print("-" * 50)
        print(f"🎉 Selesai! Total {total_deleted_all} baris data dihapus dari database.")

    except mysql.connector.Error as err:
        print(f"\n❌ Error Database: {err}")
        if conn:
            print("   Melakukan rollback (pembatalan)...")
            conn.rollback()
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            print("🔌 Koneksi ditutup.")

if __name__ == "__main__":
    delete_data_by_dates()