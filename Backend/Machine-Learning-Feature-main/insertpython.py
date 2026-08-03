import pandas as pd
import mysql.connector

# Konfigurasi MySQL
config = {
    'host': '34.128.100.191',
    'user': 'root',
    'password': 'admin',
    'database': 'emotion_trendbox'
}

# Baca CSV
csv_file = 'therest.csv'
df = pd.read_csv(csv_file)

try:
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()

    total_rows = len(df)

    # Loop setiap baris data dengan progress
    for index, row in df.iterrows():
        sql = """
            INSERT INTO emotion_track (user_id, emotion, confidence, timestamp)
            VALUES (%s, %s, %s, %s)
        """
        values = (row['user_id'], row['emotion'], float(row['confidence']), row['timestamp'])
        cursor.execute(sql, values)

        # Tampilkan progress
        progress = ((index + 1) / total_rows) * 100
        print(f"\rProgress: {index + 1}/{total_rows} ({progress:.2f}%)", end="")

    conn.commit()
    print(f"\n{total_rows} data berhasil dimasukkan ke tabel emotion_track.")

    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print("\nError:", err)
