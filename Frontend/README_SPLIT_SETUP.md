# Trendbox Frontend - Laptop Backend/Frontend

Folder ini disiapkan untuk dijalankan di laptop lain bersama backend utama.
Realtime detection tetap diarahkan ke laptop GPU/detection.

## Setup awal

```cmd
cd C:\Trendbox\Frontend
npm install
copy .env.local.example .env.local
notepad .env.local
```

Isi `.env.local` sesuai IP:

```env
NEXT_PUBLIC_API_BASE_URL=http://IP-LAPTOP-BACKEND:5000
NEXT_PUBLIC_REPORT_API_BASE_URL=http://IP-LAPTOP-BACKEND:5002
NEXT_PUBLIC_NLP_API_BASE_URL=http://IP-LAPTOP-BACKEND:5003
NEXT_PUBLIC_REALTIME_API_URL=http://IP-LAPTOP-DETECTION:5001
```

Kalau frontend dan backend utama jalan di laptop yang sama, boleh pakai `127.0.0.1` untuk port 5000/5002/5003.
Realtime tetap pakai IP laptop detection.

## Jalankan untuk akses lokal saja

```cmd
npm run dev
```

## Jalankan agar bisa dibuka device lain di jaringan LAN

```cmd
npm run dev:lan
```

atau double click:

```text
start-frontend-lan.bat
```

Lalu buka dari device lain:

```text
http://IP-LAPTOP-BACKEND:3000
```
