from flask import Flask, request, send_file
from flask_socketio import SocketIO
from flask_cors import CORS
import cv2
import numpy as np
import base64
import re
import threading
import time 
import json
from datetime import datetime
import os
import csv
import ssl
from collections import deque

# Import Logic Tracking
import apisql
from apisql import EmotionTracker, GLOBAL_MODELS

# MQTT
try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    print("âš ï¸ paho-mqtt not installed")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'development-only')

# --- UBAH ASYNC_MODE MENJADI 'threading' ---
# Ini mencegah konflik dengan TensorFlow/OpenCV
origins_env = os.getenv('FRONTEND_ORIGINS', '*')
allowed_origins = '*' if origins_env.strip() == '*' else [
    origin.strip() for origin in origins_env.split(',') if origin.strip()
]
socketio = SocketIO(app, cors_allowed_origins=allowed_origins, async_mode='threading')
CORS(app, origins=allowed_origins)

client_sessions = {}
REALTIME_LOGS = deque(maxlen=200)


def publish_log(level, message, sid=None):
    payload = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message,
        "sid": sid,
    }
    REALTIME_LOGS.append(payload)
    print(f"[{level.upper()}] {message}")
    try:
        socketio.emit("realtime_log", payload, room=sid if sid else None)
    except Exception:
        pass


apisql.LOG_HOOK = publish_log


@app.route("/")
def index():
    return {
        "status": "ok",
        "service": "Trendbox Realtime Detection API",
        "socketio": "/socket.io/",
        "health": "/health",
    }


@app.route("/health")
def health():
    return {
        "status": "ok",
        "service": "realtime-detection",
        "active_sessions": len(client_sessions),
        "models": {
            "emotion": "emotion_model" in GLOBAL_MODELS,
            "head_yolo": "yolo_head" in GLOBAL_MODELS,
            "clothing_yolo": "yolo_clothes" in GLOBAL_MODELS,
        },
    }


@app.route("/logs")
def logs():
    return {"logs": list(REALTIME_LOGS)}

# MQTT Configuration with TLS and Authentication
MQTT_ENABLED = os.getenv('MQTT_ENABLED', 'false').lower() in ('1', 'true', 'yes')
MQTT_BROKER = os.getenv('MQTT_BROKER', '')
MQTT_PORT = int(os.getenv('MQTT_PORT', '8883'))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'sensor/environment')
MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')
MQTT_USE_TLS = os.getenv('MQTT_USE_TLS', 'true').lower() in ('1', 'true', 'yes')

# Log file path - SINGLE FILE
LOG_DIR = 'sensor_logs'
LOG_FILE = os.path.join(LOG_DIR, 'sensor_data.csv')
os.makedirs(LOG_DIR, exist_ok=True)

# Lock untuk thread-safe file writing
log_lock = threading.Lock()

def init_log_file():
    """Initialize log file with header if not exists"""
    if not os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['temperature', 'humidity', 'lux', 'timestamp'])
            print(f"âœ… Log file created: {LOG_FILE}")
        except Exception as e:
            print(f"âŒ Error creating log file: {e}")

def log_sensor_data(data):
    """Write sensor data to single CSV file"""
    try:
        with log_lock:
            with open(LOG_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    data.get('temperature', 'N/A'),
                    data.get('humidity', 'N/A'),
                    data.get('light', 'N/A'),
                    data['timestamp']
                ])
        print(f"âœ… Sensor data logged: T={data.get('temperature')}Â°C, "
              f"H={data.get('humidity')}%, L={data.get('light')}lux")
    except Exception as e:
        print(f"âŒ Error logging sensor data: {e}")

def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    """MQTT connection callback"""
    if reason_code == 0:
        print("âœ… Connected to MQTT Broker with TLS")
        client.subscribe(MQTT_TOPIC)
        print(f"âœ… Subscribed to topic: {MQTT_TOPIC}")
    else:
        print(f"âŒ Failed to connect to MQTT Broker, reason code: {reason_code}")

def on_mqtt_message(client, userdata, msg):
    """MQTT message callback"""
    try:
        payload = msg.payload.decode('utf-8')
        sensor_data = json.loads(payload)
        
        print(f"ðŸ“¥ MQTT Received: Temp={sensor_data.get('temperature')}Â°C, "
              f"Humidity={sensor_data.get('humidity')}%, "
              f"Light={sensor_data.get('light')}lux")
        
        # Log to file
        log_sensor_data(sensor_data)
        
        # Broadcast to all connected clients (optional)
        socketio.emit('sensor_data', sensor_data)
        
    except Exception as e:
        print(f"âŒ Error processing MQTT message: {e}")

def on_mqtt_disconnect(client, userdata, flags, reason_code, properties):
    """MQTT disconnect callback"""
    print(f"âš ï¸ Disconnected from MQTT Broker, reason code: {reason_code}")

def init_mqtt_subscriber():
    if not MQTT_ENABLED:
        print("MQTT subscriber disabled")
        return None
    """Initialize MQTT subscriber with TLS and authentication"""
    if not HAS_MQTT:
        print("âš ï¸ MQTT not available, sensor logging disabled")
        return
    
    try:
        # Create MQTT client with callback API version 2
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        
        # Set username and password
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        # Configure TLS/SSL
        if MQTT_USE_TLS:
            mqtt_client.tls_set(
                ca_certs=None,
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                ciphers=None
            )
            # For self-signed certificates, you can disable hostname verification
            # mqtt_client.tls_insecure_set(True)
            print("ðŸ”’ TLS/SSL enabled")
        
        # Set callbacks
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_message = on_mqtt_message
        mqtt_client.on_disconnect = on_mqtt_disconnect
        
        # Connect to broker
        print(f"ðŸ”Œ Connecting to MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Start loop in background
        mqtt_client.loop_start()
        
        print(f"âœ… MQTT subscriber initialized")
        
    except Exception as e:
        print(f"âŒ Failed to initialize MQTT subscriber: {e}")
        import traceback
        traceback.print_exc()

# ============================================================
#                  CLIENT CONNECTION HANDLERS
# ============================================================

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    client_sessions[sid] = EmotionTracker(sid)
    socketio.emit("realtime_log_history", {"logs": list(REALTIME_LOGS)}, room=sid)
    publish_log("info", f"Client connected: {sid}", sid=sid)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in client_sessions:
        tracker = client_sessions[sid]
        
        # SAVE SEMUA ORANG YANG MASIH AKTIF
        print(f"[Disconnect] Saving {len(tracker.people)} people before shutdown")
        for p in tracker.people:
            if not p.saved:
                tracker.save_person(p)
        
        tracker.stop()
        del client_sessions[sid]
    publish_log("info", f"Client disconnected: {sid}", sid=sid)

# ============================================================
#                     UPDATE CONFIG
# ============================================================

@socketio.on('update_config')
def handle_config(data):
    sid = request.sid
    if sid in client_sessions:
        client_sessions[sid].update_settings(data)
        publish_log("info", f"Config updated: {data}", sid=sid)

# =================================================
#                   WEBCAM STREAM HANDLER
# ============================================================

# app.py
import time

# Global dict untuk tracking last process time per session
last_process_time = {}
processing_sessions = set()
processing_lock = threading.Lock()
INFERENCE_CONCURRENCY = max(1, int(os.getenv('INFERENCE_CONCURRENCY', '1')))
inference_slots = threading.BoundedSemaphore(INFERENCE_CONCURRENCY)
MIN_FRAME_INTERVAL = max(0.0, float(os.getenv('MIN_FRAME_INTERVAL', '0.08')))
OUTPUT_JPEG_QUALITY = min(95, max(20, int(os.getenv('OUTPUT_JPEG_QUALITY', '55'))))
RTSP_MAX_WIDTH = max(160, int(os.getenv('RTSP_MAX_WIDTH', '640')))
VERBOSE_FRAME_LOGS = os.getenv('VERBOSE_FRAME_LOGS', 'false').lower() in ('1', 'true', 'yes')

@socketio.on('inference_image')
def handle_inference(data):
    sid = request.sid
    if sid not in client_sessions:
        print(f"âš  [{sid}] Session not found!")
        return

    # âœ… RATE LIMITING: Skip frame jika terlalu cepat
    current_time = time.time()
    if sid in last_process_time:
        elapsed = current_time - last_process_time[sid]
        if elapsed < MIN_FRAME_INTERVAL:
            if VERBOSE_FRAME_LOGS:
                print(f"⏭️ [{sid}] Frame skipped - too fast ({elapsed:.3f}s)")
            return
    
    last_process_time[sid] = current_time

    with processing_lock:
        if sid in processing_sessions:
            if VERBOSE_FRAME_LOGS:
                print(f"⏭️ [{sid}] Frame skipped - previous frame still processing")
            return
        processing_sessions.add(sid)

    tracker = client_sessions[sid]

    try:
        # Decode Base64 Image
        image_payload = data.get('image')
        if isinstance(image_payload, (bytes, bytearray, memoryview)):
            np_arr = np.frombuffer(image_payload, np.uint8)
        else:
            img_data = re.sub(r'^data:image/.+;base64,', '', image_payload or '')
            np_arr = np.frombuffer(base64.b64decode(img_data), np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # ===== VALIDASI FRAME LENGKAP =====
        if frame is None:
            publish_log("warn", "Failed to decode frame: None", sid=sid)
            return
        
        if frame.size == 0:
            publish_log("warn", "Failed to decode frame: empty frame", sid=sid)
            return
        
        if len(frame.shape) != 3 or frame.shape[2] != 3:
            publish_log("warn", f"Invalid frame shape: {frame.shape}", sid=sid)
            return
        
        if frame.shape[0] < 10 or frame.shape[1] < 10:
            publish_log("warn", f"Frame too small: {frame.shape}", sid=sid)
            return
        # ==================================

        if VERBOSE_FRAME_LOGS:
            print(f"📥 [{sid}] Frame received: {frame.shape}")

        started_at = time.perf_counter()
        with inference_slots:
            processed = tracker.process_frame(frame)
        processing_ms = round((time.perf_counter() - started_at) * 1000, 1)
        people = tracker.get_people_json()

        if VERBOSE_FRAME_LOGS:
            print(f"✅ [{sid}] Processed: {len(people)} people detected")

        # Encode Result
        ok, buffer = cv2.imencode(
            '.jpg', processed,
            [int(cv2.IMWRITE_JPEG_QUALITY), OUTPUT_JPEG_QUALITY],
        )
        if not ok:
            raise RuntimeError('Failed to encode inference result')
        img_b64 = base64.b64encode(buffer).decode('utf-8')

        # Kirim hasil hanya ke client pengirim agar tidak menambah traffic client lain.
        socketio.emit('result_data', {
            "image": "data:image/jpeg;base64," + img_b64,
            "people": people,
            "count": len(people),
            "processing_ms": processing_ms,
            "fps": round(1000 / processing_ms, 1) if processing_ms > 0 else 0,
            "source": sid  # Tambahkan info source
        }, room=sid)

    except Exception as e:
        publish_log("error", f"Error inference: {e}", sid=sid)
        import traceback
        traceback.print_exc()
    finally:
        with processing_lock:
            processing_sessions.discard(sid)

# ============================================================
#                 RTSP STREAM PROCESSOR
# ============================================================

def process_rtsp_stream(sid, rtsp_url):
    tracker = client_sessions.get(sid)
    if tracker is None:
        return

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print("[RTSP] Gagal membuka stream")
        socketio.emit("rtsp_error", {"error": "Invalid RTSP URL"}, room=sid)
        return

    print(f"[RTSP] STARTED for {sid}")

    while tracker.running and sid in client_sessions:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        # Bound decode/inference cost for high-resolution RTSP sources.
        if frame.shape[1] > RTSP_MAX_WIDTH:
            scale = RTSP_MAX_WIDTH / frame.shape[1]
            frame = cv2.resize(
                frame,
                (RTSP_MAX_WIDTH, max(1, round(frame.shape[0] * scale))),
                interpolation=cv2.INTER_AREA,
            )

        started_at = time.perf_counter()
        with inference_slots:
            processed = tracker.process_frame(frame)
        processing_ms = round((time.perf_counter() - started_at) * 1000, 1)
        people = tracker.get_people_json()

        ok, buffer = cv2.imencode(
            '.jpg', processed,
            [int(cv2.IMWRITE_JPEG_QUALITY), OUTPUT_JPEG_QUALITY],
        )
        if not ok:
            continue
        img_b64 = base64.b64encode(buffer).decode('utf-8')

        socketio.emit("result_data", {
            "image": "data:image/jpeg;base64," + img_b64,
            "people": people,
            "count": len(people),
            "processing_ms": processing_ms,
            "fps": round(1000 / processing_ms, 1) if processing_ms > 0 else 0,
        }, room=sid)

        # Penting: Beri jeda agar CPU tidak 100%
        time.sleep(0.01)

    cap.release()
    print(f"[RTSP] STOPPED for {sid}")

# ============================================================
#                     START RTSP HANDLER
# ============================================================

@socketio.on("start_rtsp")
def start_rtsp_handler(data):
    sid = request.sid
    url = data.get("url")
    
    if sid not in client_sessions:
        return

    # Jalankan di Thread terpisah (Native Threading)
    t = threading.Thread(target=process_rtsp_stream, args=(sid, url))
    t.daemon = True
    t.start()

# ============================================================
#                 DOWNLOAD LOG ENDPOINTS
# ============================================================

# ============================================================
#                     DOWNLOAD LOG FILE
# ============================================================

@app.route('/download_log')
def download_log():
    """Download emotion detection log (from apisql.py EmotionTracker)"""
    try:
        # Pastikan nama file sama dengan yang di Class EmotionTracker
        log_file = 'log_detection_result.csv'
        if os.path.exists(log_file):
            return send_file(log_file, as_attachment=True, download_name='log_detection_result.csv')
        else:
            return {"error": "Log file not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/download_sensor_log')
def download_sensor_log():
    """Download sensor data log"""
    try:
        if os.path.exists(LOG_FILE):
            return send_file(LOG_FILE, as_attachment=True, download_name='sensor_data.csv')
        else:
            return {"error": "Sensor log file not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/set_config', methods=['POST'])
def set_global_config():
    """Update global confidence threshold (currently not used by models)"""
    try:
        data = request.get_json()
        threshold = data.get('confidence_threshold', 0.5)
        print(f"[Config] Global confidence threshold set to: {threshold}")
        # Note: MediaPipe uses 0.5 fixed, YOLO uses 0.4 fixed in current implementation
        return {"status": "ok", "threshold": threshold}
    except Exception as e:
        return {"error": str(e)}, 500

# ============================================================

if __name__ == "__main__":
    # Initialize log file
    init_log_file()
    
    # Initialize MQTT subscriber
    init_mqtt_subscriber()
    
    # allow_unsafe_werkzeug=True kadang diperlukan di beberapa env developmen
    socketio.run(app, host="0.0.0.0", port=5001, debug=False, allow_unsafe_werkzeug=True)
