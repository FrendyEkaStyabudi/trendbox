"""
analisis_emosi.py

Script ini diadaptasi untuk membaca `DATASETDESEMBEREMOTION.csv`.
Fungsi: Parsing timestamp, menghitung fluktuasi harian (total & per-emosi),
lalu menyimpan hasil sebagai CSV dan Grafik (PNG).

Cara Pakai:
1. Pastikan file 'DATASETDESEMBEREMOTION.csv' ada di folder yang sama dengan script ini.
2. Jalankan via terminal/CMD:
   python analisis_emosi.py
"""
import os
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from dateutil import parser as date_parser
from datetime import timedelta

def parse_timestamps(col: pd.Series) -> pd.Series:
    """Parse mixed-format datetime strings robustly."""
    parsed = pd.to_datetime(col, errors="coerce")
    if parsed.isna().any():
        mask = parsed.isna()
        # apply only to failed values
        parsed_vals = col[mask].apply(lambda x: date_parser.parse(x) if pd.notnull(x) else pd.NaT)
        parsed.loc[mask] = parsed_vals
    return parsed

def analyze_file_with_filter(path: str, start_date=None, end_date=None, label_candidates=('emotion', 'clothing_label', 'label')):
    name = os.path.splitext(os.path.basename(path))[0]
    print(f"Processing {path} -> source name: {name}")

    df = pd.read_csv(path)
    df['source'] = name

    # Detect label column (Prioritaskan 'emotion' sesuai dataset baru)
    label_col = None
    for c in label_candidates:
        if c in df.columns:
            label_col = c
            break
    if label_col is None:
        raise KeyError(f"Tidak ditemukan kolom label pada {path}. Cari salah satu: {label_candidates}")

    # Parse timestamps
    if 'timestamp' not in df.columns:
        raise KeyError(f"Tidak menemukan kolom 'timestamp' di {path}")
    
    df['timestamp'] = parse_timestamps(df['timestamp'])
    
    # Filter by date range if requested
    if start_date is not None:
        df = df[df['timestamp'].dt.date >= start_date]
    if end_date is not None:
        df = df[df['timestamp'].dt.date <= end_date]

    if df.empty:
        print(f"Peringatan: Tidak ada data dalam rentang tanggal untuk {path} (start={start_date}, end={end_date})")
        return None

    # --- 1. Fluktuasi Total per Hari ---
    daily_total = df.groupby(df['timestamp'].dt.date).size()
    daily_total.index.name = 'Tanggal'
    
    range_suffix = f"{start_date}_to_{end_date}" if start_date is not None else "all_time"
    csv_total = f'fluktuasi_harian_total_{name}_{range_suffix}.csv'
    png_total = f'fluktuasi_harian_total_{name}_{range_suffix}.png'
    
    daily_total.to_csv(csv_total, header=['count'])

    plt.figure(figsize=(12, 6))
    daily_total.plot(kind='line', marker='o', color='tab:blue')
    plt.title(f'Fluktuasi Total per Hari - {name}')
    plt.xlabel('Tanggal')
    plt.ylabel('Jumlah Event')
    plt.xticks(rotation=45)
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.savefig(png_total)
    plt.close()

    print(f"Saved: {csv_total}, {png_total}")

    # --- 2. Fluktuasi per Label (Emotion) per Hari ---
    daily_per_label = df.groupby([df['timestamp'].dt.date, df[label_col]]).size().unstack(fill_value=0)
    csv_label = f'fluktuasi_harian_per_label_{name}_{range_suffix}.csv'
    png_label = f'fluktuasi_harian_per_label_{name}_{range_suffix}.png'
    
    daily_per_label.to_csv(csv_label)

    # Plotting top labels only to avoid clutter
    top_labels = daily_per_label.sum().nlargest(8).index.tolist()
    to_plot = daily_per_label[top_labels]
    
    plt.figure(figsize=(14, 8))
    to_plot.plot(kind='line', linewidth=1.5, marker='.')
    plt.title(f'Fluktuasi Harian per Label (Top {len(top_labels)}) - {name}')
    plt.xlabel('Tanggal')
    plt.ylabel('Jumlah')
    plt.xticks(rotation=45)
    plt.legend(title=label_col)
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.savefig(png_label)
    plt.close()

    print(f"Saved: {csv_label}, {png_label}")
    
    return {
        'source': name,
        'csv_total': csv_total,
        'csv_label': csv_label,
        'rows': len(df)
    }

def main():
    parser = argparse.ArgumentParser(description='Generate daily fluctuation CSV/PNG for Emotion Dataset')
    parser.add_argument('--last-days', type=int, default=30,
                        help='Show only the last N days (default: 30). Use 0 to disable filtering.')
    parser.add_argument('--start', type=str, default=None, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None, help='End date (YYYY-MM-DD)')
    args = parser.parse_args()

    # --- BAGIAN INI DIUBAH UNTUK MENCARI DATASET BARU ANDA ---
    expected = ['dec2025_emotion_data_indonesia.csv'] 
    
    # Cek keberadaan file
    found = [p for p in expected if os.path.exists(p)]
    if not found:
        print(f"Error: File {expected[0]} tidak ditemukan di direktori ini.")
        print("Pastikan file CSV berada di folder yang sama dengan script ini.")
        sys.exit(1)

    results = []
    for p in found:
        try:
            # Pre-read untuk menentukan tanggal maksimal (untuk logika last-days)
            df_temp = pd.read_csv(p)
            if 'timestamp' not in df_temp.columns:
                print(f"Skipping {p}: no timestamp column")
                continue
                
            df_temp['timestamp'] = parse_timestamps(df_temp['timestamp'])
            max_date = df_temp['timestamp'].dt.date.max()

            # Tentukan range filter
            if args.start:
                start_date = pd.to_datetime(args.start).date()
            elif args.last_days and args.last_days > 0:
                start_date = (max_date - timedelta(days=args.last_days - 1))
            else:
                start_date = None

            if args.end:
                end_date = pd.to_datetime(args.end).date()
            else:
                end_date = max_date

            # Jalankan analisis
            res = analyze_file_with_filter(p, start_date=start_date, end_date=end_date)
            if res:
                results.append(res)
                
        except Exception as e:
            print(f"Error processing {p}: {e}")
            import traceback
            traceback.print_exc()

    print('\nSummary Processed:')
    for r in results:
        print(r)

if __name__ == '__main__':
    main()