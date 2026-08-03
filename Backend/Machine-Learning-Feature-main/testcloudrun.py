# import mysql.connector
# from tabulate import tabulate

# # Ganti dengan config milikmu
# config = {
#     'host': '34.128.100.191',      # IP publik Cloud SQL
#     'user': 'root',
#     'password': 'admin',           # ganti sesuai password MySQL-mu
#     'database': 'emotion_trendbox'
# }

# try:
#     conn = mysql.connector.connect(**config)
#     cursor = conn.cursor(dictionary=True)

#     query = "SELECT * FROM emotion_track ORDER BY id DESC LIMIT 20"
#     cursor.execute(query)

#     results = cursor.fetchall()

#     if results:
#         headers = results[0].keys()
#         rows = [row.values() for row in results]
#         print(tabulate(rows, headers=headers, tablefmt="grid"))
#     else:
#         print("No data found.")

#     cursor.close()
#     conn.close()

# except mysql.connector.Error as err:
#     print("Connection error:", err)


import cv2

url = "rtsp://admin:AHZLPA@10.99.241.28:554/Streaming/Channels/102"
cap = cv2.VideoCapture(url)

print("Opened:", cap.isOpened())

ret, frame = cap.read()
print("Frame:", ret)
print(cv2.getBuildInformation())