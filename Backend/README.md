# Trendbox Backend - Laptop Backend/Frontend

Folder ini disiapkan untuk laptop lain yang menjalankan backend utama, bukan realtime ML.

## Service yang dijalankan default

- Dashboard API: http://127.0.0.1:5000
- Reports API: http://127.0.0.1:5002
- NLP Chatbot API: http://127.0.0.1:5003

Realtime ML API port 5001 tidak dijalankan default, karena dijalankan di laptop GPU/detection.

## Cara menjalankan

```cmd
cd C:\Trendbox\Backend
python run_backends.py
```

Atau double click:

```text
start-backend-only.bat
```

Kalau benar-benar ingin menjalankan semua termasuk realtime ML di folder ini:

```cmd
python run_backends.py --include-realtime
```

## Database

Default database lokal:

```text
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_DATABASE=trendbox
DB_NAME=trendbox
```

Pastikan database `trendbox` sudah diimport di MySQL/Laragon laptop ini.

## Akses dari laptop lain

Backend Flask sudah bind ke `0.0.0.0`, jadi dari device lain gunakan IP laptop ini:

```text
http://IP-LAPTOP-BACKEND:5000
http://IP-LAPTOP-BACKEND:5002
http://IP-LAPTOP-BACKEND:5003
```

Windows Firewall harus mengizinkan Python pada Private Network.

## Realtime Detection

Realtime detection tetap dijalankan di laptop GPU/detection:

```cmd
cd C:\Trendbox\Backend\Machine-Learning-Feature-main
python app.py
```

Frontend harus diarahkan ke URL laptop detection, contoh:

```text
NEXT_PUBLIC_REALTIME_API_URL=http://192.168.1.30:5001
```
