import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


def load_env_file(path):
    if not path.exists():
        return {}

    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


DEFAULT_DB_ENV = {
    "DB_HOST": os.getenv("DB_HOST", "127.0.0.1"),
    "DB_PORT": os.getenv("DB_PORT", "5432"),
    "DB_USER": os.getenv("DB_USER", "postgres"),
    "DB_PASSWORD": os.getenv("DB_PASSWORD", ""),
    "DB_DATABASE": os.getenv("DB_DATABASE", os.getenv("DB_NAME", "postgres")),
    "DB_NAME": os.getenv("DB_NAME", os.getenv("DB_DATABASE", "postgres")),
    "FRONTEND_ORIGINS": os.getenv("FRONTEND_ORIGINS", "*"),
}

DEFAULT_DB_ENV.update(load_env_file(ROOT / ".env"))

SERVICES = [
    {
        "name": "Dashboard API",
        "port": 5000,
        "cwd": ROOT / "DMPKENV-main",
        "entry": "integrated.py",
        "env": DEFAULT_DB_ENV,
    },
    {
        "name": "Realtime ML API",
        "port": 5001,
        "cwd": ROOT / "Machine-Learning-Feature-main",
        "entry": "app.py",
        "optional": True,
        "env": DEFAULT_DB_ENV,
    },
    {
        "name": "Reports API",
        "port": 5002,
        "cwd": ROOT / "REPORTENV-main",
        "entry": "app.py",
        "env": DEFAULT_DB_ENV,
    },
    {
        "name": "NLP Chatbot API",
        "port": 5003,
        "cwd": ROOT / "API-NLP-CHATBOT-QUERY-GENERATOR-main",
        "entry": "app.py",
        "env": DEFAULT_DB_ENV,
    },
]


def parse_args():
    parser = argparse.ArgumentParser(description="Run Trendbox backend services.")
    parser.add_argument(
        "--include-realtime",
        action="store_true",
        help="Also run Realtime ML API on port 5001. Default is off because ML runs on the GPU/detection laptop.",
    )
    return parser.parse_args()


def start_service(service):
    env = os.environ.copy()
    env.update({
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    env.update(service.get("env", {}))

    entry = service["cwd"] / service["entry"]
    if not entry.exists():
        raise FileNotFoundError(f"Missing entry file for {service['name']}: {entry}")

    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{service['port']}-{service['name'].lower().replace(' ', '-')}.log"
    log_file = open(log_path, "a", encoding="utf-8", errors="replace")

    process = subprocess.Popen(
        [PYTHON, service["entry"]],
        cwd=service["cwd"],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    return process, log_file, log_path


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        process.send_signal(signal.CTRL_BREAK_EVENT)
        time.sleep(1)
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def main():
    args = parse_args()
    services = [
        service for service in SERVICES
        if args.include_realtime or service.get("name") != "Realtime ML API"
    ]

    print("Starting Trendbox backend services from:", ROOT)
    print("Python:", PYTHON)
    print("Mode:", "backend + realtime" if args.include_realtime else "backend only (Realtime ML runs on GPU/detection laptop)")
    print()

    running = []
    try:
        for service in services:
            process, log_file, log_path = start_service(service)
            running.append((service, process, log_file, log_path))
            print(f"[STARTED] {service['name']} on http://127.0.0.1:{service['port']}  pid={process.pid}")
            print(f"          LAN URL example: http://IP-LAPTOP-BACKEND:{service['port']}")
            print(f"          log: {log_path}")
            time.sleep(1)

        print()
        print("Backend services were started.")
        print("Default mode does NOT start Realtime ML API.")
        print("Run Realtime ML on the GPU/detection laptop and set frontend NEXT_PUBLIC_REALTIME_API_URL to that laptop IP.")
        print("Press Ctrl+C here to stop these backend services.")
        print()

        reported_stops = set()
        while True:
            for service, process, _log_file, log_path in running:
                code = process.poll()
                if code is not None and service["name"] not in reported_stops:
                    reported_stops.add(service["name"])
                    print(f"[STOPPED] {service['name']} exited with code {code}. Check {log_path}")
                    print("          Other backend services are still running.")
            time.sleep(2)
    except KeyboardInterrupt:
        print("Stopping backend services...")
    finally:
        for service, process, log_file, _log_path in reversed(running):
            print(f"Stopping {service['name']}...")
            stop_process(process)
            log_file.close()
        print("Done.")


if __name__ == "__main__":
    main()
