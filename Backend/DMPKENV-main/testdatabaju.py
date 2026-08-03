# 1. Import library yang diperlukan
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import glob
import os
from dateutil import parser as date_parser

try:
    # Gunakan khusus `data_kepala.csv` dan `data_baju.csv` seperti diminta
    expected = ["data_kepala_shifted.csv", "data_baju_shifted.csv"]
    data_files = [f for f in expected if os.path.exists(f)]
    if not data_files:
        raise FileNotFoundError(f"Tidak ditemukan salah satu file {expected} di direktori saat ini.")

    # Baca dan gabungkan semua file data, tambahkan kolom 'source' untuk menandai asal file
    df_list = []
    for f in data_files:
        tmp = pd.read_csv(f)
        tmp['source'] = os.path.splitext(os.path.basename(f))[0]
        df_list.append(tmp)

    df = pd.concat(df_list, ignore_index=True)

    # Ubah kolom 'timestamp' menjadi format datetime — tahan terhadap format campuran
    def parse_timestamps(col):
        # Pertama coba parsing vektor cepat (kebanyakan baris)
        parsed = pd.to_datetime(col, errors='coerce', infer_datetime_format=True)
        # Untuk nilai yang gagal, gunakan dateutil yang lebih fleksibel
        if parsed.isna().any():
            mask = parsed.isna()
            parsed_vals = col[mask].apply(lambda x: date_parser.parse(x) if pd.notnull(x) else pd.NaT)
            parsed.loc[mask] = parsed_vals
        return parsed

    df['timestamp'] = parse_timestamps(df['timestamp'])

    # Jika masih ada nilai yang tidak ter-parse, laporkan baris contohnya untuk debugging
    if df['timestamp'].isna().any():
        bad_idx = df[df['timestamp'].isna()].index[:5].tolist()
        sample_bad = df.loc[bad_idx, 'timestamp'].astype(str).tolist()
        raise ValueError(f"Beberapa nilai timestamp gagal di-parse. Contoh: {sample_bad}")

    print("--- Info Tipe Data Kolom (Seluruh Data Gabungan) ---")
    df.info()
    print("\n" + "="*40 + "\n")

    # Pilih kolom label yang tersedia (beberapa file pakai 'emotion', yang lain 'clothing_label')
    label_col = None
    for candidate in ('emotion', 'clothing_label', 'label'):
        if candidate in df.columns:
            label_col = candidate
            break
    if label_col is None:
        raise KeyError('Tidak ditemukan kolom label (cari salah satu: emotion, clothing_label, label)')

    # ANALISIS: Jumlah Total Tiap Kategori
    print(f"--- Analisis: Jumlah Total Tiap Kategori (Semua Data) berdasarkan '{label_col}' ---")
    total_emotion_counts = df[label_col].value_counts()
    print(total_emotion_counts)
    print("\n" + "="*40 + "\n")

    # ANALISIS 1: Jumlah tiap data (emotion) dalam sehari
    print("--- Analisis: Jumlah per Tipe per Hari ---")
    jumlah_per_hari_per_jenis = df.groupby([df['timestamp'].dt.date, df[label_col]]).size().reset_index(name='jumlah')
    print(jumlah_per_hari_per_jenis)
    print("\n" + "="*40 + "\n")

    # ANALISIS 2: Fluktuasi per Jam (Total semua jenis data)
    print("--- Analisis: Fluktuasi Total per Jam (0-23) ---")
    fluktuasi_per_jam = df.groupby(df['timestamp'].dt.hour).size().reindex(range(24), fill_value=0)
    fluktuasi_per_jam.index.name = 'Jam'
    print(fluktuasi_per_jam)
    print("\n" + "="*40 + "\n")

    # DIAGRAM: Membuat diagram batang untuk fluktuasi per jam
    print("Membuat diagram fluktuasi per jam...")
    plt.figure(figsize=(12, 7))
    fluktuasi_per_jam.plot(kind='bar', color='deepskyblue', width=0.8)

    plt.title('Diagram Fluktuasi Data per Jam', fontsize=16)
    plt.xlabel('Jam dalam Sehari (0-23)', fontsize=12)
    plt.ylabel('Jumlah Data (Event)', fontsize=12)
    plt.xticks(ticks=range(24), labels=range(24), rotation=0)

    ax = plt.gca()
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()

    nama_file_plot = "fluktuasi_per_jam.png"
    plt.savefig(nama_file_plot)
    print(f"Diagram berhasil disimpan sebagai {nama_file_plot}")

    # plt.show() # Aktifkan baris ini jika Anda menjalankan di komputer lokal

    # --- Analisis Tambahan: Fluktuasi Harian per Sumber (kepala / baju) ---
    print("Menganalisis fluktuasi harian terpisah untuk setiap sumber (kepala & baju)...")

    for src in df['source'].unique():
        subset = df[df['source'] == src].copy()
        # pastikan subset tidak kosong
        if subset.empty:
            continue

        # Fluktuasi total per hari untuk sumber ini
        daily_total_src = subset.groupby(subset['timestamp'].dt.date).size()
        daily_total_src.index.name = 'Tanggal'

        nama_file_daily_total = f'fluktuasi_harian_total_{src}.png'
        plt.figure(figsize=(12, 6))
        daily_total_src.plot(kind='line', marker='o', color='tab:blue')
        plt.title(f'Fluktuasi Total per Hari - {src}', fontsize=14)
        plt.xlabel('Tanggal', fontsize=12)
        plt.ylabel('Jumlah Event', fontsize=12)
        plt.xticks(rotation=45)
        plt.grid(axis='y', linestyle='--', alpha=0.6)
        plt.tight_layout()
        plt.savefig(nama_file_daily_total)
        print(f"Diagram harian total untuk {src} disimpan sebagai {nama_file_daily_total}")

        # Simpan daily total ke CSV
        csv_total_name = f'fluktuasi_harian_total_{src}.csv'
        daily_total_src.to_csv(csv_total_name, header=['count'])

        # Fluktuasi per label per hari untuk sumber ini
        daily_per_label_src = subset.groupby([subset['timestamp'].dt.date, subset[label_col]]).size().unstack(fill_value=0)
        csv_label_name = f'fluktuasi_harian_per_label_{src}.csv'
        daily_per_label_src.to_csv(csv_label_name)
        print(f"Tabel harian per label untuk {src} disimpan sebagai {csv_label_name}")

        # Plot top labels untuk sumber ini
        top_labels_src = daily_per_label_src.sum().nlargest(8).index.tolist()
        to_plot_src = daily_per_label_src[top_labels_src].copy()
        plt.figure(figsize=(14, 8))
        to_plot_src.plot(kind='line', linewidth=1)
        plt.title(f'Fluktuasi Harian per Label (Top {len(top_labels_src)}) - {src}', fontsize=14)
        plt.xlabel('Tanggal', fontsize=12)
        plt.ylabel('Jumlah', fontsize=12)
        plt.xticks(rotation=45)
        plt.legend(title=label_col)
        plt.grid(axis='y', linestyle='--', alpha=0.6)
        plt.tight_layout()
        nama_file_daily_label = f'fluktuasi_harian_per_label_{src}.png'
        plt.savefig(nama_file_daily_label)
        print(f"Diagram harian per label untuk {src} disimpan sebagai {nama_file_daily_label}")

except FileNotFoundError as e:
    print(f"Error: {e}")
except KeyError as e:
    print(f"Error: Kolom {e} tidak ditemukan. Periksa nama kolom di file CSV Anda.")
except Exception as e:
    print(f"Terjadi error: {e}")