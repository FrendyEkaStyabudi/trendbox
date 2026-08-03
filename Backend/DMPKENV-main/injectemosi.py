import mysql.connector
import os
import pandas as pd
import sys

# --- Konfigurasi Database (Sesuai request Anda) ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'yamanote.proxy.rlwy.net'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu'),
    'database': os.getenv('DB_DATABASE', 'railway'),
    'port': int(os.getenv('DB_PORT', 59862)),
}

# --- Konfigurasi File ---
CSV_FILENAME = 'dec2025_emotion_data_indonesia.csv'
TABLE_NAME = 'emotion_track'

def inject_data_from_csv():
    """Membaca CSV dan melakukan INSERT data ke database."""
    
    conn = None
    
    # 1. Cek apakah file CSV ada
    if not os.path.exists(CSV_FILENAME):
        print(f"❌ Error: File '{CSV_FILENAME}' tidak ditemukan.")
        return

    try:
        # 2. Baca CSV menggunakan Pandas
        print(f"📖 Membaca file {CSV_FILENAME}...")
        df = pd.read_csv(CSV_FILENAME)
        
        # Bersihkan data: ubah NaN menjadi None agar diterima MySQL
        df = df.where(pd.notnull(df), None)
        
        total_data = len(df)
        print(f"📊 Ditemukan {total_data} baris data untuk di-inject.")

        # 3. Koneksi ke Database
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print(f"✅ Berhasil terhubung ke database '{DB_CONFIG['database']}'.")

        # 4. Siapkan Query INSERT
        # Catatan: Kita SKIP kolom 'id' dari CSV dan membiarkan Database membuat ID otomatis (Auto Increment)
        # agar tidak terjadi error "Duplicate Entry" jika ID sudah ada.
        query = f"""
            INSERT INTO {TABLE_NAME} (user_id, emotion, confidence, timestamp)
            VALUES (%s, %s, %s, %s)
        """

        # 5. Konversi Dataframe ke list of tuples untuk eksekusi massal
        # Pastikan urutan kolom di sini sama dengan urutan di Query VALUES
        data_to_insert = []
        for index, row in df.iterrows():
            data_to_insert.append((
                row['user_id'], 
                row['emotion'], 
                row['confidence'], 
                row['timestamp']
            ))

        # 6. Eksekusi Inject (Batch Insert)
        print("🚀 Sedang melakukan injeksi data...")
        cursor.executemany(query, data_to_insert)
        
        conn.commit()
        rows_inserted = cursor.rowcount
        
        print("-" * 50)
        print(f"🎉 Sukses! Total {rows_inserted} baris data berhasil ditambahkan ke tabel '{TABLE_NAME}'.")
        print("-" * 50)

    except mysql.connector.Error as err:
        print(f"\n❌ Gagal Database! Error: {err}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"\n❌ Gagal Umum! Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            print("🔌 Koneksi database ditutup.")

if __name__ == "__main__":
    inject_data_from_csv()