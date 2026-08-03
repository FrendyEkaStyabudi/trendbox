# Trendbox

Trendbox adalah platform analitik emosi dan atribut visual berbasis web yang dikembangkan oleh **PNJ Team**. Platform ini menggabungkan deteksi real-time melalui browser atau edge device, dashboard analitik, forecasting, laporan, dan asisten SQL berbasis bahasa alami dalam satu antarmuka yang responsif.

## Aplikasi

[Buka Trendbox](https://trendbox-web-590242083739.asia-southeast2.run.app/)

## Fitur Utama

- Deteksi emosi dan atribut visual secara real-time
- Inferensi langsung di browser menggunakan WebGPU dengan fallback WebAssembly
- Integrasi opsional dengan API deteksi dari Jetson atau Raspberry Pi
- Dashboard untuk emosi, atribut pakaian, dan atribut kepala
- Distribusi data historis dan tren real-time
- Forecasting untuk data emosi dan atribut
- Insight, laporan, dan ekspor data
- Pertanyaan bahasa alami yang diterjemahkan menjadi query SQL read-only
- Antarmuka responsif untuk desktop dan perangkat mobile

## Arsitektur

```text
Browser / Edge Device
        |
        v
Frontend Next.js (port 3000)
        |
        +-- Dashboard API (Flask, port 5000)
        +-- Reports API   (Flask, port 5002)
        +-- NLP API       (Flask, port 5003)
        |
        v
MySQL / Google Cloud SQL
```

Deteksi melalui browser memuat model ONNX dari lokasi penyimpanan model yang telah dikonfigurasi. Perangkat Jetson dan Raspberry Pi dapat digunakan sebagai alternatif dengan menyediakan API real-time yang dimasukkan melalui halaman Real-time Tracking.

## Teknologi yang Digunakan

| Bagian | Teknologi |
| --- | --- |
| Frontend | Next.js 15, React 18, TypeScript, Tailwind CSS |
| UI dan grafik | Radix UI, Recharts, Chart.js |
| Inferensi browser | ONNX Runtime Web, WebGPU, WebAssembly, MediaPipe |
| Backend | Python, Flask, Gunicorn |
| Database | MySQL / Google Cloud SQL |
| Forecasting | Prophet, pandas, scikit-learn |
| NLP | API LLM yang kompatibel dengan Groq dan SQL read-only |
| Cloud | Google Cloud Run, Cloud SQL, Cloud Storage, Secret Manager |

## Struktur Repositori

```text
Trendbox/
|-- Frontend/                                  # Aplikasi Next.js
|-- Backend/
|   |-- DMPKENV-main/                         # Dashboard dan forecasting API
|   |-- REPORTENV-main/                       # Reports API
|   |-- API-NLP-CHATBOT-QUERY-GENERATOR-main/ # NLP assistant API
|   |-- Machine-Learning-Feature-main/        # API ML real-time opsional
|   `-- run_backends.py                       # Menjalankan service backend lokal
|-- gcs-model-cors.json                       # Konfigurasi CORS bucket model
`-- README.md
```

## Persyaratan Sistem

- Node.js 20 atau lebih baru
- npm
- Python 3.11
- MySQL 8.0
- Git
- Groq API key untuk NLP assistant
- Browser yang mendukung WebGPU untuk akselerasi inferensi browser (opsional)

## Menjalankan Secara Lokal

### 1. Kloning repositori

```bash
git clone https://github.com/FrendyEkaStyabudi/trendbox.git
cd trendbox
```

### 2. Konfigurasi MySQL

Buat database dengan nama `trendbox`, kemudian terapkan schema yang tersedia:

```bash
mysql -u root -p trendbox < Backend/DMPKENV-main/schema.sql
```

Untuk membuat ulang database lokal sekaligus mengimpor data CSV yang tersedia:

```bash
cd Backend/DMPKENV-main
python rebuild_local_db.py --reset
cd ../..
```

Opsi `--reset` akan mengosongkan tabel tracking Trendbox sebelum mengimpor data. Jangan gunakan opsi tersebut apabila data yang sudah ada harus dipertahankan.

### 3. Konfigurasi dan jalankan backend

Windows PowerShell atau Command Prompt:

```bat
cd Backend
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r DMPKENV-main\requirements.txt
pip install -r REPORTENV-main\requirements.txt
pip install -r API-NLP-CHATBOT-QUERY-GENERATOR-main\requirements.txt
copy .env.example .env
```

Sesuaikan isi `Backend/.env`:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=trendbox-app
DB_PASSWORD=password-database-anda
DB_DATABASE=trendbox
DB_NAME=trendbox
FRONTEND_ORIGINS=http://localhost:3000
GROQ_API_KEY=groq-api-key-server-anda
GROQ_MODEL_NAME=llama-3.1-8b-instant
```

Jalankan tiga API utama:

```bat
python run_backends.py
```

Alamat service lokal:

| Service | URL |
| --- | --- |
| Dashboard API | `http://127.0.0.1:5000` |
| Reports API | `http://127.0.0.1:5002` |
| NLP API | `http://127.0.0.1:5003` |

Untuk ikut menjalankan API ML real-time secara lokal:

```bat
python run_backends.py --include-realtime
```

### 4. Konfigurasi dan jalankan frontend

Buka terminal baru:

```bat
cd Frontend
npm ci
copy .env.local.example .env.local
```

Untuk menggunakan seluruh API lokal, sesuaikan `Frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:5000
NEXT_PUBLIC_REPORT_API_BASE_URL=http://127.0.0.1:5002
NEXT_PUBLIC_NLP_API_BASE_URL=http://127.0.0.1:5003
NEXT_PUBLIC_WEBGPU_FRAME_INTERVAL_MS=180
NEXT_PUBLIC_MODEL_BASE_URL=/models
```

Jalankan development server:

```bat
npm.cmd run dev
```

Buka <http://localhost:3000>.

Untuk membuka frontend dari perangkat lain dalam jaringan yang sama:

```bat
npm.cmd run dev:lan
```

Kemudian buka `http://IP-LAN-KOMPUTER-ANDA:3000` dari perangkat lain. Pastikan Windows Firewall mengizinkan Node.js dan service Python yang diperlukan pada jaringan privat.

## Variabel Environment

### Frontend

| Variabel | Kegunaan |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | URL Dashboard dan Forecasting API |
| `NEXT_PUBLIC_REPORT_API_BASE_URL` | URL Reports API |
| `NEXT_PUBLIC_NLP_API_BASE_URL` | URL NLP Assistant API |
| `NEXT_PUBLIC_MODEL_BASE_URL` | Direktori model ONNX atau URL bucket model |
| `NEXT_PUBLIC_WEBGPU_FRAME_INTERVAL_MS` | Jeda antar-frame inferensi browser |
| `NEXT_PUBLIC_REALTIME_API_URL` | URL default API Jetson/Raspberry Pi yang bersifat opsional |

### Backend

| Variabel | Kegunaan |
| --- | --- |
| `DB_HOST`, `DB_PORT` | Koneksi jaringan MySQL |
| `DB_USER`, `DB_PASSWORD` | Kredensial MySQL |
| `DB_DATABASE`, `DB_NAME` | Nama database Trendbox |
| `INSTANCE_CONNECTION_NAME` | Nama koneksi Cloud SQL untuk Cloud Run |
| `FRONTEND_ORIGINS` | Origin frontend yang diizinkan oleh CORS |
| `GROQ_API_KEY` | Kredensial NLP provider pada sisi server |
| `GROQ_MODEL_NAME` | Nama model NLP |

Variabel dengan awalan `NEXT_PUBLIC_` akan dikirim ke browser. Jangan pernah menyimpan password, kredensial database, atau private API key di dalam variabel tersebut.

## Membuat Build Production

```bat
cd Frontend
npm.cmd run build
npm.cmd run start
```

Direktori frontend dan masing-masing API juga menyediakan Dockerfile untuk deployment menggunakan container. Pada Google Cloud, simpan kredensial di Secret Manager dan hubungkan Cloud SQL ke service Cloud Run terkait. Jangan menyimpan kredensial di dalam repositori.

## Pemeriksaan Service

Setelah menjalankan backend, periksa status setiap service:

```bat
curl.exe http://127.0.0.1:5000/health
curl.exe http://127.0.0.1:5002/health
curl.exe http://127.0.0.1:5003/health
```

## Alur Kerja Git yang Direkomendasikan

Branch `master` digunakan untuk kode stabil yang telah diuji. Lakukan pengembangan aktif pada branch `development` atau feature branch, kemudian gabungkan ke `master` setelah seluruh pemeriksaan lokal berhasil.

```bash
git switch -c development
git add .
git commit -m "feat: tingkatkan aplikasi Trendbox"
git push -u origin development
```

Untuk perubahan yang lebih besar, buat branch baru dari `development`:

```bash
git switch development
git switch -c feature/chat-layout
```

Alur branch yang direkomendasikan:

```text
feature/* -> development -> master
```

Sebelum menggabungkan perubahan ke `master`, jalankan:

```bat
cd Frontend
npm.cmd exec tsc -- --noEmit
npm.cmd run build
```

## Keamanan

- Jangan commit file `.env` atau `.env.local`.
- Simpan kredensial production di Google Secret Manager.
- Batasi origin CORS saat digunakan pada production.
- Gunakan user database khusus dengan izin minimum yang diperlukan aplikasi.
- Segera rotasi kredensial apabila pernah masuk ke dalam riwayat Git.

## Tim

Dibuat dan dikelola oleh **PNJ Team**.
