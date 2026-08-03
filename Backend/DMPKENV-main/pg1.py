import pandas as pd
import os

# --- KONFIGURASI ---
INPUT_FILE = "data_kepala.csv"
OUTPUT_FILE = "data_kepala_filtered.csv"  # Nama file baru
CUTOFF_DATE = "2025-12-24"  # Data mulai tanggal ini akan DIHAPUS (Jadi 23 Des adalah hari terakhir yang disimpan)

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"File {INPUT_FILE} tidak ditemukan.")
        return

    print(f"Membaca {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"Gagal membaca file: {e}")
        return

    # 1. Cari kolom timestamp
    cols_lower = {c.lower(): c for c in df.columns}
    col_ts = next((name for low, name in cols_lower.items() if 'timestamp' in low), None)

    if not col_ts:
        print("Gagal: Kolom 'timestamp' tidak ditemukan.")
        return

    # 2. Konversi ke Datetime
    print(f"Kolom waktu terdeteksi: '{col_ts}'")
    df[col_ts] = pd.to_datetime(df[col_ts], errors='coerce')

    # 3. Filter Data
    # Logika: Ambil data yang KURANG DARI tanggal cutoff (24 Des 00:00:00)
    # Artinya data tanggal 23 Des 23:59:59 masih MASUK.
    cutoff_ts = pd.Timestamp(CUTOFF_DATE)
    
    initial_count = len(df)
    df_filtered = df[df[col_ts] < cutoff_ts]
    final_count = len(df_filtered)
    
    removed_count = initial_count - final_count

    # 4. Format ulang timestamp ke string (agar rapi di CSV)
    df_filtered[col_ts] = df_filtered[col_ts].dt.strftime('%Y-%m-%dT%H:%M:%S')

    # Jika ada kolom 'tanggal' terpisah, update juga agar sinkron
    col_date = next((name for low, name in cols_lower.items() if 'tanggal' in low or 'date' in low), None)
    if col_date:
        df_filtered[col_date] = pd.to_datetime(df_filtered[col_ts]).dt.strftime('%Y-%m-%d')

    # 5. Simpan ke file baru
    try:
        df_filtered.to_csv(OUTPUT_FILE, index=False)
        print("-" * 30)
        print(f"SUKSES!")
        print(f"Total data awal   : {initial_count}")
        print(f"Data dibuang      : {removed_count} (Data mulai {CUTOFF_DATE} ke atas)")
        print(f"Data tersimpan    : {final_count}")
        print(f"File baru disimpan: {OUTPUT_FILE}")
        print("-" * 30)
    except Exception as e:
        print(f"Gagal menyimpan file baru: {e}")

if __name__ == "__main__":
    main()