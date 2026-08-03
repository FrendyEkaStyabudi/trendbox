import pandas as pd
from datetime import datetime, timedelta

# Load CSV
df = pd.read_csv("may_2025_emotion_data_indonesia - Copy.csv")  # Ganti dengan nama file CSV kamu

# Ubah kolom 'timestamp' jadi format datetime
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Ambil waktu sekarang (sama seperti CURRENT_TIMESTAMP() di SQL)
now = datetime.now()

# Batas waktu 7 hari terakhir
last_7_days = now - timedelta(days=7)

# Filter data:
filtered_df = df[
    (df['emotion'] == 'happy') & 
    (df['timestamp'] >= last_7_days)
]

# Hitung jumlahnya
count_happy = filtered_df.shape[0]

print(f"Jumlah 'happy' dalam 7 hari terakhir: {count_happy}")

# (Optional) Tampilkan data yang terfilter
print(filtered_df)
