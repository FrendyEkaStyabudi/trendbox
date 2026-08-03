"""
fluktuasi_terpisah.py

Standalone script: baca `data_kepala.csv` dan `data_baju.csv`, parsing timestamp yang
mungkin berupa ISO (T) atau spasi, lalu simpan fluktuasi harian (total & per-label)
sebagai CSV dan PNG terpisah untuk setiap sumber.

Jalankan dari folder proyek dengan venv Python Anda, contoh:
& "C:/.../.venv/Scripts/python.exe" "./fluktuasi_terpisah.py"
"""
import os
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from dateutil import parser as date_parser
from datetime import timedelta


def parse_timestamps(col: pd.Series) -> pd.Series:
    """Parse mixed-format datetime strings robustly.
    - Coba vectorized pd.to_datetime pertama (fast)
    - Untuk nilai yang gagal, fallback ke dateutil.parser.parse
    """
    parsed = pd.to_datetime(col, errors="coerce")
    if parsed.isna().any():
        mask = parsed.isna()
        # apply only to failed values
        parsed_vals = col[mask].apply(lambda x: date_parser.parse(x) if pd.notnull(x) else pd.NaT)
        parsed.loc[mask] = parsed_vals
    return parsed


def analyze_file(path: str, label_candidates=('emotion', 'clothing_label', 'label')):
    name = os.path.splitext(os.path.basename(path))[0]
    print(f"Processing {path} -> source name: {name}")

    df = pd.read_csv(path)
    # add source column
    df['source'] = name

    # detect label column
    label_col = None
    for c in label_candidates:
        if c in df.columns:
            label_col = c
            break
    if label_col is None:
        raise KeyError(f"Tidak ditemukan kolom label pada {path}. Cari salah satu: {label_candidates}")

    # parse timestamps robustly
    if 'timestamp' not in df.columns:
        raise KeyError(f"Tidak menemukan kolom 'timestamp' di {path}")
    df['timestamp'] = parse_timestamps(df['timestamp'])
    if df['timestamp'].isna().any():
        bad = df[df['timestamp'].isna()].head(5)
        raise ValueError(f"Beberapa timestamp gagal di-parse di {path}. Contoh: {bad['timestamp'].tolist()}")

    # Fluktuasi total per hari
    daily_total = df.groupby(df['timestamp'].dt.date).size()
    daily_total.index.name = 'Tanggal'
    csv_total = f'fluktuasi_harian_total_{name}.csv'
    png_total = f'fluktuasi_harian_total_{name}.png'
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

    # Fluktuasi per label per hari
    daily_per_label = df.groupby([df['timestamp'].dt.date, df[label_col]]).size().unstack(fill_value=0)
    csv_label = f'fluktuasi_harian_per_label_{name}.csv'
    png_label = f'fluktuasi_harian_per_label_{name}.png'
    daily_per_label.to_csv(csv_label)

    # choose top labels for plotting
    top_labels = daily_per_label.sum().nlargest(8).index.tolist()
    to_plot = daily_per_label[top_labels]
    plt.figure(figsize=(14, 8))
    to_plot.plot(kind='line', linewidth=1)
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
        'png_total': png_total,
        'csv_label': csv_label,
        'png_label': png_label,
        'rows': len(df)
    }


def main():
    parser = argparse.ArgumentParser(description='Generate daily fluctuation CSV/PNG per source')
    parser.add_argument('--last-days', type=int, default=30,
                        help='Show only the last N days ending at the latest date in each file (default: 30). Use 0 to disable filtering.')
    parser.add_argument('--start', type=str, default=None, help='Start date (YYYY-MM-DD) to filter data. Overrides --last-days if provided.')
    parser.add_argument('--end', type=str, default=None, help='End date (YYYY-MM-DD) to filter data. Overrides --last-days if provided.')
    args = parser.parse_args()

    expected = ['data_kepala.csv', 'data_baju.csv']
    found = [p for p in expected if os.path.exists(p)]
    if not found:
        print(f"Error: tidak ditemukan file salah satu dari {expected} di direktori saat ini.")
        sys.exit(1)

    results = []
    for p in found:
        try:
            # read and parse first to get max date
            df_temp = pd.read_csv(p)
            if 'timestamp' not in df_temp.columns:
                print(f"Skipping {p}: no timestamp column")
                continue
            df_temp['timestamp'] = parse_timestamps(df_temp['timestamp'])
            max_date = df_temp['timestamp'].dt.date.max()

            # determine filtering range
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

            # call analyze_file but pass filtering info via a wrapper
            res = analyze_file_with_filter(p, start_date=start_date, end_date=end_date)
            results.append(res)
        except Exception as e:
            print(f"Error processing {p}: {e}")

    print('\nSummary:')
    for r in results:
        print(r)


def analyze_file_with_filter(path: str, start_date=None, end_date=None, label_candidates=('emotion', 'clothing_label', 'label')):
    # read original file and apply same parsing/detection as analyze_file
    name = os.path.splitext(os.path.basename(path))[0]
    df = pd.read_csv(path)
    df['source'] = name
    label_col = None
    for c in label_candidates:
        if c in df.columns:
            label_col = c
            break
    if label_col is None:
        raise KeyError(f"Tidak ditemukan kolom label pada {path}. Cari salah satu: {label_candidates}")
    df['timestamp'] = parse_timestamps(df['timestamp'])

    # filter by date range if requested
    if start_date is not None:
        df = df[df['timestamp'].dt.date >= start_date]
    if end_date is not None:
        df = df[df['timestamp'].dt.date <= end_date]

    if df.empty:
        raise ValueError(f"Tidak ada data dalam rentang tanggal untuk {path} (start={start_date}, end={end_date})")

    # proceed to generate outputs (reuse code in analyze_file)
    # Fluktuasi total per hari
    daily_total = df.groupby(df['timestamp'].dt.date).size()
    daily_total.index.name = 'Tanggal'
    # include date range in filenames for clarity
    range_suffix = f"{start_date}_to_{end_date}" if start_date is not None else f"to_{end_date}"
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

    # Fluktuasi per label per hari
    daily_per_label = df.groupby([df['timestamp'].dt.date, df[label_col]]).size().unstack(fill_value=0)
    csv_label = f'fluktuasi_harian_per_label_{name}_{range_suffix}.csv'
    png_label = f'fluktuasi_harian_per_label_{name}_{range_suffix}.png'
    daily_per_label.to_csv(csv_label)

    # choose top labels for plotting
    top_labels = daily_per_label.sum().nlargest(8).index.tolist()
    to_plot = daily_per_label[top_labels]
    plt.figure(figsize=(14, 8))
    to_plot.plot(kind='line', linewidth=1)
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
        'png_total': png_total,
        'csv_label': csv_label,
        'png_label': png_label,
        'rows': len(df),
        'start_date': start_date,
        'end_date': end_date
    }


if __name__ == '__main__':
    main()
