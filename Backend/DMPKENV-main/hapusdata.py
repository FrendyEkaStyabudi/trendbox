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

# --- Daftar Data yang DIPERBOLEHKAN (Whitelist) ---
# Data selain yang ada di list ini akan DIHAPUS.

# Catatan: Saya menggunakan ejaan 'surprised' (dengan 'r') karena itu standar dataset umum.
# Jika di database Anda tersimpan sebagai 'suprised' (typo), silakan ubah di list ini.
ALLOWED_EMOTIONS = ['sad', 'happy', 'angry', 'fear', 'surprised']

ALLOWED_CLOTHES = ['sweater', 'shorts', 'skirt', 'long_pants', 't-shirt', 'shirt', 'blouse', 'outer']

ALLOWED_HEAD = ['hat', 'hair', 'hijab']

def clean_invalid_data():
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print(f"✅ Terhubung ke database: {DB_CONFIG['database']}")
        print("-" * 50)

        # ---------------------------------------------------------
        # 1. Bersihkan tabel EMOTION_TRACK
        # ---------------------------------------------------------
        # Buat string SQL: "'sad', 'happy', 'angry', ..."
        emotions_str = ", ".join([f"'{x}'" for x in ALLOWED_EMOTIONS])
        query_emotion = f"DELETE FROM emotion_track WHERE emotion NOT IN ({emotions_str})"
        
        print(f"🧹 [emotion_track] Menghapus data selain: {ALLOWED_EMOTIONS}")
        cursor.execute(query_emotion)
        print(f"   👉 {cursor.rowcount} baris dihapus.")

        # ---------------------------------------------------------
        # 2. Bersihkan tabel CLOTHES_TRACK
        # ---------------------------------------------------------
        # ASUMSI: Nama kolom label baju adalah 'label'. 
        # Jika error "Unknown column", ganti 'label' di bawah menjadi 'clothing_label' atau sesuai database Anda.
        clothes_col_name = 'label' 
        
        clothes_str = ", ".join([f"'{x}'" for x in ALLOWED_CLOTHES])
        query_clothes = f"DELETE FROM clothing_track WHERE {clothes_col_name} NOT IN ({clothes_str})"
        
        print(f"\n🧹 [clothes_track] Menghapus data selain: {ALLOWED_CLOTHES}")
        try:
            cursor.execute(query_clothes)
            print(f"   👉 {cursor.rowcount} baris dihapus.")
        except mysql.connector.Error as err:
            print(f"   ❌ Gagal: {err}")
            print(f"      (Tips: Cek apakah nama kolomnya benar '{clothes_col_name}'?)")

        # ---------------------------------------------------------
        # 3. Bersihkan tabel HEAD_TRACK
        # ---------------------------------------------------------
        # ASUMSI: Nama kolom label kepala adalah 'label'.
        head_col_name = 'label'

        head_str = ", ".join([f"'{x}'" for x in ALLOWED_HEAD])
        query_head = f"DELETE FROM head_track WHERE {head_col_name} NOT IN ({head_str})"
        
        print(f"\n🧹 [head_track] Menghapus data selain: {ALLOWED_HEAD}")
        try:
            cursor.execute(query_head)
            print(f"   👉 {cursor.rowcount} baris dihapus.")
        except mysql.connector.Error as err:
            print(f"   ❌ Gagal: {err}")

        # ---------------------------------------------------------
        # Commit perubahan
        conn.commit()
        print("-" * 50)
        print("🎉 Selesai! Semua data sampah telah dihapus.")

    except mysql.connector.Error as err:
        print(f"\n❌ Terjadi Error Database: {err}")
        if conn:
            print("   Melakukan rollback (pembatalan)...")
            conn.rollback()
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            print("🔌 Koneksi ditutup.")

if __name__ == "__main__":
    clean_invalid_data()