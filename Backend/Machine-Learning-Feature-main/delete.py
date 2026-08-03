import mysql.connector

# Config database Cloud SQL kamu
config = {
    'host': '34.128.100.191',
    'user': 'root',
    'password': 'admin',
    'database': 'emotion_trendbox'
}

try:
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()

    # Hapus semua data di tabel emotion_track
    cursor.execute("DELETE FROM emotion_track;")
    conn.commit()

    print("Semua data di tabel emotion_track sudah dihapus.")

    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print("Connection error:", err)
