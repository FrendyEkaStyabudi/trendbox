import mysql.connector

# Konfigurasi MySQL
config = {
    'host': '34.128.100.191',
    'user': 'root',
    'password': 'admin',
    'database': 'emotion_trendbox'
}

try:
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()

    # Query untuk menghitung jumlah data
    cursor.execute("SELECT COUNT(*) FROM emotion_track;")
    result = cursor.fetchone()

    print(f"Jumlah data di tabel emotion_track: {result[0]}")

    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print("Error:", err)
