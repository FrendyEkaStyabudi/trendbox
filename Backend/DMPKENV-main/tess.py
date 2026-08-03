import mysql.connector
import pandas as pd
import os

# --- Konfigurasi Database (Sama seperti di aplikasi Flask Anda) ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'yamanote.proxy.rlwy.net'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu'),
    'database': os.getenv('DB_DATABASE', 'railway'),
    'port': int(os.getenv('DB_PORT', 59862)),
}

# --- Daftar Tanggal yang Ingin Diperiksa ---
DATES_TO_QUERY = ['2025-10-22', '2025-10-23', '2025-10-24']

def run_queries_for_date(target_date):
    """Menyambungkan ke DB dan menjalankan semua query untuk satu tanggal."""
    print(f"\n{'='*20} HASIL UNTUK TANGGAL: {target_date} {'='*20}")
    
    conn = None
    try:
        # Membuat koneksi
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 1. Query dari /api/summary - Menghitung total deteksi
        print("\n--- 1. Ringkasan (Summary) ---")
        query_total_count = "SELECT COUNT(*) AS count FROM emotion_track WHERE DATE(timestamp) = %s"
        cursor.execute(query_total_count, (target_date,))
        result_count = cursor.fetchone()
        print(f"Total Deteksi: {result_count['count'] if result_count else 0}")

        # 2. Query dari /api/summary - Mencari emosi dominan
        query_dominant = """
            SELECT emotion FROM emotion_track 
            WHERE DATE(timestamp) = %s 
            GROUP BY emotion ORDER BY COUNT(*) DESC LIMIT 1
        """
        cursor.execute(query_dominant, (target_date,))
        result_dominant = cursor.fetchone()
        print(f"Emosi Dominan: {result_dominant['emotion'] if result_dominant else 'N/A'}")

        # 3. Query dari /api/distribution - Menggunakan pandas untuk tabel yang lebih rapi
        print("\n--- 2. Distribusi Emosi ---")
        query_dist = "SELECT emotion, COUNT(*) AS count FROM emotion_track WHERE DATE(timestamp) = %s GROUP BY emotion"
        df_dist = pd.read_sql(query_dist, conn, params=(target_date,))
        
        if df_dist.empty:
            print("Tidak ada data distribusi ditemukan.")
        else:
            print(df_dist.to_string(index=False))

        # 4. Query dari /api/trends/today - Menggunakan pandas
        print("\n--- 3. Tren Emosi Per Jam ---")
        query_trends = """
            SELECT emotion, HOUR(timestamp) AS hour, COUNT(*) AS count 
            FROM emotion_track WHERE DATE(timestamp) = %s 
            GROUP BY emotion, hour ORDER BY hour
        """
        df_trends = pd.read_sql(query_trends, conn, params=(target_date,))
        
        if df_trends.empty:
            print("Tidak ada data tren per jam ditemukan.")
        else:
            print(df_trends.to_string(index=False))
            
    except mysql.connector.Error as err:
        print(f"Error Database: {err}")
    except Exception as e:
        print(f"Terjadi error: {e}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            # print(f"\nKoneksi untuk tanggal {target_date} ditutup.")

# --- Loop utama untuk menjalankan query untuk setiap tanggal ---
if __name__ == "__main__":
    for date in DATES_TO_QUERY:
        run_queries_for_date(date)
    print(f"\n{'='*58}\n")