import mysql.connector
import os

# --- Konfigurasi Database (Sama seperti sebelumnya) ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'yamanote.proxy.rlwy.net'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu'),
    'database': os.getenv('DB_DATABASE', 'railway'),
    'port': int(os.getenv('DB_PORT', 59862)),
}

# --- Parameter untuk Operasi Update ---
TARGET_DATE = '2025-09-12'
EMOTIONS_TO_CHANGE = {
    'sad': 200,
    'surprised': 200
}
NEW_EMOTION = 'happy'

def update_random_emotions():
    """Menyambungkan ke DB dan mengubah emosi secara acak berdasarkan parameter."""
    
    conn = None
    total_rows_affected = 0
    
    # Template query. Menggunakan subquery untuk memilih ID acak yang akan diupdate.
    # Ganti 'id' jika nama kolom primary key Anda berbeda.
    query_template = f"""
        UPDATE emotion_track
        SET emotion = %s
        WHERE id IN (
            SELECT id FROM (
                SELECT id FROM emotion_track
                WHERE emotion = %s AND DATE(timestamp) = %s
                ORDER BY RAND()
                LIMIT %s
            ) AS subquery
        )
    """

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print(f"✅ Berhasil terhubung ke database '{DB_CONFIG['database']}'.")
        print(f"🎯 Target: Mengubah emosi menjadi '{NEW_EMOTION}' pada tanggal {TARGET_DATE}.")
        print("-" * 50)

        # Iterasi untuk setiap emosi yang ingin diubah
        for old_emotion, limit in EMOTIONS_TO_CHANGE.items():
            params = (NEW_EMOTION, old_emotion, TARGET_DATE, limit)
            
            print(f"🔄 Mencoba mengubah {limit} data acak dari '{old_emotion}' menjadi '{NEW_EMOTION}'...")
            
            cursor.execute(query_template, params)
            rows_affected = cursor.rowcount
            total_rows_affected += rows_affected
            
            print(f"✔️ Berhasil mengubah {rows_affected} baris.")
            if rows_affected < limit:
                print(f"   (Catatan: Ditemukan {rows_affected} baris, kurang dari target {limit}.)")

        # Jika semua berhasil, commit perubahan ke database
        conn.commit()
        print("-" * 50)
        print(f"🎉 Sukses! Total {total_rows_affected} baris telah diubah di database.")
        print("Transaksi berhasil di-commit.")

    except mysql.connector.Error as err:
        print(f"\n❌ Gagal! Terjadi error pada database: {err}")
        if conn:
            print("Rollback dilakukan, tidak ada perubahan yang disimpan.")
            conn.rollback() # Batalkan semua perubahan jika terjadi error
    except Exception as e:
        print(f"\n❌ Gagal! Terjadi error tak terduga: {e}")
        if conn:
            print("Rollback dilakukan, tidak ada perubahan yang disimpan.")
            conn.rollback()
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            print("\n🔌 Koneksi ke database ditutup.")

# --- Jalankan fungsi utama ---
if __name__ == "__main__":
    update_random_emotions()