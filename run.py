import os
import sys
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

INSTANCE_CONN = os.getenv("INSTANCE_CONNECTION_NAME", "trendbox-2026:asia-southeast2:trendbox-mysql")
DB_PORT = os.getenv("DB_PORT", "3306")

ENV = os.environ.copy()
ENV.update({
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
    "DB_HOST": os.getenv("DB_HOST", "127.0.0.1"),
    "DB_PORT": DB_PORT,
    "DB_USER": os.getenv("DB_USER", "trendbox-app"),
    "DB_PASSWORD": os.getenv("DB_PASSWORD", "Trendbox-2026"),
    "DB_DATABASE": os.getenv("DB_DATABASE", "trendbox"),
    "DB_NAME": os.getenv("DB_NAME", "trendbox"),
    "INSTANCE_CONNECTION_NAME": INSTANCE_CONN,
    "FRONTEND_ORIGINS": "*",
})

# Tentukan binary Cloud SQL Proxy (GCloud)
if (ROOT / "cloud-sql-proxy.exe").exists():
    PROXY_BIN = str(ROOT / "cloud-sql-proxy.exe")
elif (ROOT / "cloud-sql-proxy").exists():
    PROXY_BIN = str(ROOT / "cloud-sql-proxy")
else:
    PROXY_BIN = "cloud-sql-proxy"

SERVICES = [
    {
        "name": "Cloud SQL Proxy (GCloud)",
        "port": int(DB_PORT),
        "cwd": ROOT,
        "cmd": [PROXY_BIN, INSTANCE_CONN, "--port", DB_PORT],
    },
    {
        "name": "Dashboard API",
        "port": 5000,
        "cwd": ROOT / "Backend" / "DMPKENV-main",
        "cmd": [PYTHON, "integrated.py"],
    },
    {
        "name": "Realtime ML API",
        "port": 5001,
        "cwd": ROOT / "Backend" / "Machine-Learning-Feature-main",
        "cmd": [PYTHON, "app.py"],
    },
    {
        "name": "Reports API",
        "port": 5002,
        "cwd": ROOT / "Backend" / "REPORTENV-main",
        "cmd": [PYTHON, "app.py"],
    },
    {
        "name": "NLP Chatbot API",
        "port": 5003,
        "cwd": ROOT / "Backend" / "API-NLP-CHATBOT-QUERY-GENERATOR-main",
        "cmd": [PYTHON, "app.py"],
    },
    {
        "name": "Frontend Next.js",
        "port": 3000,
        "cwd": ROOT / "Frontend",
        "cmd": ["npm.cmd" if os.name == "nt" else "npm", "run", "dev"],
    },
]


def main():
    print("=" * 55)
    print("        STARTING ALL TRENDBOX SERVICES (LOCALHOST)       ")
    print("=" * 55)
    print(f"Root Directory: {ROOT}")
    print("-" * 55)

    processes = []
    total_services = len(SERVICES)

    try:
        for idx, service in enumerate(SERVICES, 1):
            print(f"[{idx}/{total_services}] Starting {service['name']} (Port {service['port']})...")
            proc = subprocess.Popen(
                service["cmd"],
                cwd=service["cwd"],
                env=ENV
            )
            processes.append((service, proc))
            time.sleep(1.5)

        print("\n" + "=" * 55)
        print("✅ Semuanya telah berhasil dijalankan!\n")
        print(f"☁️ Cloud SQL Proxy (GCloud): 127.0.0.1:{DB_PORT}")
        print("🌐 Frontend App            : http://localhost:3000")
        print("⚙️ Realtime ML API         : http://localhost:5001")
        print("⚙️ Dashboard API            : http://localhost:5000")
        print("⚙️ Reports API              : http://localhost:5002")
        print("⚙️ NLP Chatbot API          : http://localhost:5003")
        print("=" * 55)
        print("\nTekan Ctrl+C di terminal ini untuk menghentikan semua service.\n")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[STOPPING] Menghentikan semua service...")
    finally:
        for service, proc in reversed(processes):
            if proc.poll() is None:
                proc.terminate()
        print("✅ Semua service telah dihentikan.")


if __name__ == "__main__":
    main()

