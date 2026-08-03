import cv2
import base64
import socketio
import time
import numpy as np
import threading
import queue
import json
from datetime import datetime
import ssl

# --- PENTING: Import Library Khusus Raspberry Pi ---
try:
    import board
    import busio
    import adafruit_dht
    import adafruit_bh1750
    HAS_SENSORS = True
except ImportError:
    HAS_SENSORS = False
    print("⚠️ Library sensor tidak ditemukan.")
    print("   Install: pip3 install adafruit-circuitpython-dht adafruit-circuitpython-bh1750 adafruit-blinka")
    print("   Pastikan juga: sudo apt-get install libgpiod2")

# MQTT
try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    print("⚠️ paho-mqtt not installed. Install: pip3 install paho-mqtt")

# --- KONFIGURASI ---
SERVER_URL = 'http://127.0.0.1:5001'

# MQTT Configuration with TLS and Authentication
MQTT_BROKER = 'aa5271d0.ala.asia-southeast1.emqxsl.com'
MQTT_PORT = 8883
MQTT_TOPIC = 'sensor/environment'
MQTT_USERNAME = 'trendbox'  # Ganti dengan username Anda
MQTT_PASSWORD = 'trendbox123'  # Ganti dengan password Anda
MQTT_USE_TLS = True

# RTSP Camera
RTSP_URL = 0

# Setting Interval & Skip
FRAME_SKIP = 3  # ✅ Skip 2 frame dari setiap 3 frame (10 FPS → 3.3 FPS)
SENSOR_INTERVAL = 5  # Detik

# Global Objects
sio = socketio.Client()
mqtt_client = None
frame_queue = queue.Queue(maxsize=2)
running = True
frame_counter = 0

# Sensor Instances
dht_device = None
bh1750_device = None

def init_sensors():
    """Inisialisasi Sensor untuk Raspberry Pi 4"""
    global dht_device, bh1750_device
    
    if not HAS_SENSORS:
        return False
    
    # 1. Inisialisasi DHT22
    # Di RPi 4, board.D4 merujuk pada GPIO 4 (Physical Pin 7)
    try:
        # use_pulseio=False disarankan untuk Raspberry Pi (Linux)
        dht_device = adafruit_dht.DHT22(board.D4, use_pulseio=False)
        print("✅ DHT22 initialized on GPIO4 (Pin 7)")
    except Exception as e:
        print(f"⚠️ Failed to init DHT22: {e}")
        dht_device = None

    # 2. Inisialisasi BH1750 (I2C)
    # Pastikan I2C sudah di-enable di raspi-config
    try:
        i2c = board.I2C()  # Menggunakan SCL(GPIO3) dan SDA(GPIO2)
        bh1750_device = adafruit_bh1750.BH1750(i2c)
        print("✅ BH1750 initialized on I2C Bus")
    except ValueError as e:
        print("⚠️ I2C Error: Pastikan I2C enabled via raspi-config.")
        print(f"   Detail: {e}")
        bh1750_device = None
    except Exception as e:
        print(f"⚠️ Failed to init BH1750: {e}")
        bh1750_device = None

    return (dht_device is not None) or (bh1750_device is not None)

def read_sensors():
    """Membaca data sensor dengan handling error khusus RPi"""
    data = {
        'timestamp': datetime.now().isoformat(),
        'temperature': None,
        'humidity': None,
        'light': None
    }
    
    # Baca DHT22
    if dht_device is not None:
        try:
            # DHT sering gagal baca di Linux, itu normal.
            t = dht_device.temperature
            h = dht_device.humidity
            if t is not None and h is not None:
                data['temperature'] = round(t, 2)
                data['humidity'] = round(h, 2)
        except RuntimeError as error:
            # RuntimeError biasa terjadi (Checksum error), abaikan saja untuk iterasi ini
            # print(f"ℹ️ DHT Read warning: {error.args[0]}") 
            pass
        except Exception as error:
            print(f"⚠️ DHT22 Fatal Error: {error}")
            # Opsional: re-init sensor jika error fatal terus menerus

    # Baca BH1750
    if bh1750_device is not None:
        try:
            l = bh1750_device.lux
            if l is not None:
                data['light'] = round(l, 2)
        except Exception as e:
            print(f"⚠️ BH1750 read error: {e}")

    return data

# --- MQTT FUNCTIONS ---
def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    """MQTT connection callback for API v2"""
    if reason_code == 0:
        print("✅ Connected to MQTT Broker with TLS")
    else:
        print(f"❌ Failed to connect to MQTT, reason code: {reason_code}")

def on_mqtt_publish(client, userdata, mid, reason_code, properties):
    """MQTT publish callback"""
    print(f"📤 Message published (mid: {mid})")

def on_mqtt_disconnect(client, userdata, flags, reason_code, properties):
    """MQTT disconnect callback"""
    print(f"⚠️ Disconnected from MQTT Broker, reason code: {reason_code}")

def init_mqtt():
    """Initialize MQTT client with TLS and authentication"""
    global mqtt_client
    
    if not HAS_MQTT:
        print("⚠️ MQTT not available")
        return False
    
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
            # For self-signed certificates, uncomment this:
            # mqtt_client.tls_insecure_set(True)
            print("🔒 TLS/SSL enabled")
        
        # Set callbacks
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_publish = on_mqtt_publish
        mqtt_client.on_disconnect = on_mqtt_disconnect
        
        # Connect to broker
        print(f"🔌 Connecting to MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        
        print(f"✅ MQTT client initialized")
        return True
        
    except Exception as e:
        print(f"❌ MQTT initialization failed: {e}")
        import traceback
        traceback.print_exc()
        mqtt_client = None
        return False

# --- WORKER THREADS ---

def sensor_thread():
    global running
    print("🌡️ Sensor thread started")
    
    sensors_ready = init_sensors()
    mqtt_ready = init_mqtt()
    
    if not sensors_ready:
        print("⚠️ No sensors active. Thread will idle.")
    
    if not mqtt_ready:
        print("⚠️ MQTT not ready. Sensor data will not be sent.")

    while running:
        start_time = time.time()
        try:
            if sensors_ready:
                sensor_data = read_sensors()
                
                # Log console (hanya jika ada data valid)
                log_msg = "📊 Sensor: "
                if sensor_data['temperature']: log_msg += f"T={sensor_data['temperature']}°C "
                if sensor_data['humidity']: log_msg += f"H={sensor_data['humidity']}% "
                if sensor_data['light']: log_msg += f"L={sensor_data['light']}lux"
                print(log_msg)

                # Kirim MQTT
                if mqtt_client and mqtt_ready:
                    # Filter data None sebelum kirim agar tidak merusak JSON parser di server
                    clean_data = {k: v for k, v in sensor_data.items() if v is not None}
                    # Tetap kirim timestamp
                    clean_data['timestamp'] = sensor_data['timestamp']
                    
                    try:
                        payload = json.dumps(clean_data)
                        result = mqtt_client.publish(MQTT_TOPIC, payload, qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            print(f"📤 Sensor data sent via MQTT (TLS)")
                        else:
                            print(f"⚠️ Failed to publish: {result.rc}")
                    except Exception as e:
                        print(f"❌ MQTT publish error: {e}")

        except Exception as e:
            print(f"❌ Sensor Loop Error: {e}")
            import traceback
            traceback.print_exc()
        
        # Smart sleep: kurangi waktu proses dari interval
        elapsed = time.time() - start_time
        sleep_time = max(0.1, SENSOR_INTERVAL - elapsed)
        time.sleep(sleep_time)
    
    # Cleanup
    if dht_device: dht_device.exit()
    if mqtt_client: 
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    print("🛑 Sensor thread stopped")

def capture_thread():
    global running
    print(f"🎥 Connecting to Camera...")
    
    # Menggunakan GStreamer backend jika tersedia di RPi (opsional, default FFMPEG oke)
    cap = cv2.VideoCapture(RTSP_URL)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Low latency buffer
    
    if not cap.isOpened():
        print("❌ Failed to open RTSP stream")
        return

    print("✅ Camera Connected")
    
    # Counter untuk tracking frame errors
    consecutive_errors = 0
    max_consecutive_errors = 10
    
    while running:
        ret, frame = cap.read()
        if ret:
            # ===== TAMBAHAN: VALIDASI FRAME DARI KAMERA =====
            if frame is None or frame.size == 0:
                print("⚠️ Received invalid frame from camera")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    print("❌ Too many consecutive errors, reconnecting...")
                    cap.release()
                    time.sleep(2)
                    cap = cv2.VideoCapture(RTSP_URL)
                    consecutive_errors = 0
                continue
            
            # Reset error counter on successful read
            consecutive_errors = 0
            # ================================================
            
            # Kosongkan queue jika penuh (drop frame lama) agar realtime
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
            
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                pass
        else:
            print("⚠️ Frame drop / Camera disconnect. Retrying...")
            consecutive_errors += 1
            cap.release()
            time.sleep(2)
            cap = cv2.VideoCapture(RTSP_URL) # Reconnect attempt
            consecutive_errors = 0
            
    cap.release()
    print("🛑 Capture thread stopped")

def send_thread():
    global running, frame_counter
    print("📤 Send thread started")
    
    while running:
        try:
            # Timeout agar thread bisa cek 'running' jika queue kosong
            frame = frame_queue.get(timeout=1)
            
            # VALIDASI FRAME - Pastikan frame valid sebelum dikirim
            if frame is None:
                print("⚠️ Skipping None frame")
                continue
            
            if frame.size == 0:
                print("⚠️ Skipping empty frame")
                continue
            
            if len(frame.shape) != 3 or frame.shape[2] != 3:
                print(f"⚠️ Skipping invalid frame shape: {frame.shape}")
                continue
            
            frame_counter += 1
            
            if frame_counter % FRAME_SKIP != 0:
                continue
            
            try:
                # Resize untuk performa RPi (640x480 cukup ringan)
                frame = cv2.resize(frame, (640, 480))
                
                # Validasi lagi setelah resize
                if frame is None or frame.size == 0:
                    print("⚠️ Frame corrupted after resize")
                    continue
                
                # Kompresi JPEG (Quality 50-70 recommended untuk RPi ke Server)
                success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])  
                
                if not success:
                    print("⚠️ Failed to encode frame to JPEG")
                    continue
                
                # ===== VALIDASI BASE64 =====
                if buffer is None or buffer.size == 0:
                    print("⚠️ Empty buffer after encoding")
                    continue
                # ===========================
                
                img_b64 = base64.b64encode(buffer).decode('utf-8')
                
                # ===== VALIDASI BASE64 STRING =====
                if not img_b64 or len(img_b64) < 100:
                    print(f"⚠️ Invalid base64 string: length={len(img_b64)}")
                    continue
                # ==================================
                
                if sio.connected:
                    sio.emit('inference_image', {'image': f'data:image/jpeg;base64,{img_b64}'})
                else:
                    print("⚠️ Socket.IO not connected, skipping frame")
                    
            except cv2.error as e:
                print(f"❌ OpenCV Error: {e}")
                continue
            except Exception as e:
                print(f"❌ Frame processing error: {e}")
                continue
            
        except queue.Empty:
            continue
        except Exception as e:
            print(f"❌ Send Error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)

    print("🛑 Send thread stopped")

# --- SOCKET.IO EVENTS ---
@sio.event
def connect():
    print("✅ Socket.IO Connected")

@sio.event
def disconnect():
    print("❌ Socket.IO Disconnected")

@sio.on('result_data')
def on_result(data):
    print(f"📥 Server Result: {data['count']} people detected")

# --- MAIN ---
if __name__ == "__main__":
    try:
        print(f"🔌 Connecting to {SERVER_URL}...")
        try:
            sio.connect(SERVER_URL)
        except Exception as e:
            print(f"⚠️ SocketIO Connection Warning: {e}")
            # Lanjut jalan meskipun socketio gagal diawal (akan auto-reconnect logic internal atau retry)

        # Start Threads
        t_cap = threading.Thread(target=capture_thread, daemon=True)
        t_send = threading.Thread(target=send_thread, daemon=True)
        t_sens = threading.Thread(target=sensor_thread, daemon=True)
        
        t_cap.start()
        t_send.start()
        t_sens.start()
        
        print("🚀 System Running. Press Ctrl+C to stop.")
        
        while running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Stopping...")
        running = False
    finally:
        if sio.connected: sio.disconnect()
        print("✅ System Shutdown")