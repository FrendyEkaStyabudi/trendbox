import os
import sys
from datetime import date
import pandas as pd

# manip_timestamp_fix.py
# Skrip: Menggeser TIMESTAMP agar dimulai dari Hari Ini.
#        Dan menyamakan kolom TANGGAL agar sinkron.

FILES = ["data_kepala.csv"]
BACKUP_SUFFIX = ".bak"

def process_file(path: str):
    if not os.path.exists(path):
        print(f"File tidak ditemukan: {path}")
        return

    print(f"\n--- Memproses {path} ---")

    try:
        # Baca CSV
        df = pd.read_csv(path, keep_default_na=False)
    except Exception as e:
        print(f"Gagal membaca {path}: {e}")
        return

    # 1. Deteksi Kolom Timestamp dan Tanggal
    cols_lower = {c.lower(): c for c in df.columns}
    
    col_ts = next((name for low, name in cols_lower.items() if 'timestamp' in low), None)
    col_date = next((name for low, name in cols_lower.items() if 'tanggal' in low or 'date' in low), None)

    if not col_ts:
        print(f"LEWATI: Tidak ditemukan kolom 'timestamp' di {path}")
        return

    print(f"Target Timestamp : {col_ts}")
    if col_date:
        print(f"Target Tanggal   : {col_date} (Akan disinkronkan)")

    try:
        # 2. Konversi ke Datetime
        df[col_ts] = pd.to_datetime(df[col_ts], errors='coerce')
        
        # Cek apakah ada data valid
        if df[col_ts].dropna().empty:
            print("Gagal: Kolom timestamp tidak berisi data waktu yang valid.")
            return

        # 3. Hitung Selisih Hari (Shift)
        # Ambil tanggal dari timestamp paling awal
        min_ts_date = df[col_ts].min().date() 
        today = date.today()
        
        # Hitung jarak hari
        delta = today - min_ts_date
        
        print(f"  - Tanggal Lama : {min_ts_date}")
        print(f"  - Target Mulai : {today}")
        print(f"  - Geser Waktu  : {delta.days} hari")

        # 4. Eksekusi Penggeseran (Jam/Menit tetap aman)
        df[col_ts] = df[col_ts] + pd.to_timedelta(delta.days, unit='D')

        # 5. Sinkronisasi Kolom Tanggal (Jika ada)
        # Mengisi kolom tanggal dengan date part dari timestamp yang baru
        if col_date:
            df[col_date] = df[col_ts].dt.date

        # 6. Formatting Kembali ke String
        # Format Timestamp ISO: 2025-11-24T13:00:00
        df[col_ts] = df[col_ts].dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        # Format Tanggal: 2025-11-24
        if col_date:
            df[col_date] = pd.to_datetime(df[col_date]).dt.strftime('%Y-%m-%d')

    except Exception as e:
        print(f"Error saat proses data: {e}")
        return

    # --- SIMPAN & BACKUP ---
    backup_path = path + BACKUP_SUFFIX
    try:
        # Buat backup
        if not os.path.exists(backup_path):
            os.replace(path, backup_path)
        else:
            # Handle existing backup
            i = 1
            while True:
                alt = f"{path}.bak{i}"
                if not os.path.exists(alt):
                    os.replace(path, alt)
                    backup_path = alt
                    break
                i += 1
        
        # Simpan file baru
        df.to_csv(path, index=False)
        print(f"SUKSES: File diperbarui. Backup di {backup_path}")
        
        # Preview
        print("Preview Data Baru:")
        cols_to_show = [col_ts]
        if col_date: cols_to_show.append(col_date)
        print(df[cols_to_show].head(3))

    except Exception as e:
        print(f"Gagal menyimpan file: {e}")
        # Restore jika gagal
        if os.path.exists(backup_path):
            os.replace(backup_path, path)

def main():
    for fname in FILES:
        process_file(fname)

if __name__ == "__main__":
    main()