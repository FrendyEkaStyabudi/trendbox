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

# --- REALSENSE IMPORT ---
try:
    import pyrealsense2 as rs
    HAS_REALSENSE = True
except ImportError:
    HAS_REALSENSE = False
    print("Library pyrealsense2 not found.")
    print("Install with: pip install pyrealsense2")

# --- MQTT IMPORT ---
try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    print("paho-mqtt not installed. Install: pip install paho-mqtt")

# --- SENSORS IMPORT ---
try:
    import board
    import adafruit_dht
    import adafruit_bh1750
    HAS_SENSORS = True
except ImportError:
    HAS_SENSORS = False
    print("Sensor libraries not installed.")
    print("Install: pip install adafruit-circuitpython-dht adafruit-circuitpython-bh1750")

# --- CONFIG ---
SERVER_URL = 'http://192.168.0.123:5001'

MQTT_BROKER = 'aa5271d0.ala.asia-southeast1.emqxsl.com'
MQTT_PORT = 8883
MQTT_TOPIC = 'sensor/environment'
MQTT_USERNAME = 'trendbox'
MQTT_PASSWORD = 'trendbox123'
MQTT_USE_TLS = True

FRAME_SKIP = 3
SENSOR_INTERVAL = 5

sio = socketio.Client()
mqtt_client = None
frame_queue = queue.Queue(maxsize=2)
running = True
frame_counter = 0

dht_device = None
bh1750_device = None

def init_sensors():
    global dht_device, bh1750_device
    
    if not HAS_SENSORS:
        return False
    
    try:
        dht_device = adafruit_dht.DHT22(board.D4, use_pulseio=False)
        print("DHT22 initialized on GPIO4")
    except Exception as e:
        print(f"Failed to init DHT22: {e}")
        dht_device = None

    try:
        i2c = board.I2C()
        bh1750_device = adafruit_bh1750.BH1750(i2c)
        print("BH1750 initialized on I2C Bus")
    except Exception as e:
        print(f"Failed to init BH1750: {e}")
        bh1750_device = None

    return (dht_device is not None) or (bh1750_device is not None)

def read_sensors():
    data = {
        'timestamp': datetime.now().isoformat(),
        'temperature': None,
        'humidity': None,
        'light': None
    }
    
    if dht_device is not None:
        try:
            t = dht_device.temperature
            h = dht_device.humidity
            if t is not None and h is not None:
                data['temperature'] = round(t, 2)
                data['humidity'] = round(h, 2)
        except RuntimeError:
            pass
        except Exception as error:
            print(f"DHT22 Fatal Error: {error}")

    if bh1750_device is not None:
        try:
            l = bh1750_device.lux
            if l is not None:
                data['light'] = round(l, 2)
        except Exception as e:
            print(f"BH1750 read error: {e}")

    return data

# --- MQTT FUNCTIONS ---
def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker with TLS")
    else:
        print(f"Failed to connect MQTT, reason code: {reason_code}")

def on_mqtt_publish(client, userdata, mid, reason_code, properties):
    print(f"Message published (mid: {mid})")

def on_mqtt_disconnect(client, userdata, flags, reason_code, properties):
    print(f"Disconnected from MQTT Broker, reason code: {reason_code}")

def init_mqtt():
    global mqtt_client
    
    if not HAS_MQTT:
        print("MQTT not available")
        return False
    
    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        if MQTT_USE_TLS:
            mqtt_client.tls_set(
                ca_certs=None,
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                ciphers=None
            )
            print("TLS/SSL enabled")
        
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_publish = on_mqtt_publish
        mqtt_client.on_disconnect = on_mqtt_disconnect
        
        print(f"Connecting MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        
        print("MQTT client initialized")
        return True
        
    except Exception as e:
        print(f"MQTT initialization failed: {e}")
        import traceback
        traceback.print_exc()
        mqtt_client = None
        return False

# --- THREADS ---

def sensor_thread():
    global running
    print("Sensor thread started")
    
    sensors_ready = init_sensors()
    mqtt_ready = init_mqtt()
    
    if not sensors_ready:
        print("No sensors active. Idle.")
    
    if not mqtt_ready:
        print("MQTT not ready. No sensor data sent.")

    while running:
        start_time = time.time()
        try:
            if sensors_ready:
                sensor_data = read_sensors()
                
                log_msg = "Sensor: "
                if sensor_data['temperature']: log_msg += f"T={sensor_data['temperature']}C "
                if sensor_data['humidity']: log_msg += f"H={sensor_data['humidity']}% "
                if sensor_data['light']: log_msg += f"L={sensor_data['light']}lux"
                print(log_msg)

                if mqtt_client and mqtt_ready:
                    clean_data = {k: v for k, v in sensor_data.items() if v is not None}
                    clean_data['timestamp'] = sensor_data['timestamp']
                    
                    try:
                        payload = json.dumps(clean_data)
                        result = mqtt_client.publish(MQTT_TOPIC, payload, qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            print("Sensor data sent via MQTT (TLS)")
                        else:
                            print(f"Publish failed: {result.rc}")
                    except Exception as e:
                        print(f"MQTT publish error: {e}")

        except Exception as e:
            print(f"Sensor Loop Error: {e}")
            import traceback
            traceback.print_exc()
        
        elapsed = time.time() - start_time
        sleep_time = max(0.1, SENSOR_INTERVAL - elapsed)
        time.sleep(sleep_time)
    
    if dht_device:
        dht_device.exit()
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    print("Sensor thread stopped")

def capture_thread():
    global running
    
    if not HAS_REALSENSE:
        print("RealSense library not found. Capture thread stopped.")
        return

    print("Initializing RealSense D455...")
    
    pipeline = rs.pipeline()
    config = rs.config()

    consecutive_errors = 0
    max_consecutive_errors = 10

    try:
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        pipeline.start(config)
        print("RealSense stream started successfully")
    except Exception as e:
        print(f"Failed to start RealSense: {e}")
        running = False
        return

    while running:
        try:
            frames = pipeline.wait_for_frames(timeout_ms=5000)
            color_frame = frames.get_color_frame()
            
            if not color_frame:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    print("Too many errors, restarting pipeline...")
                    pipeline.stop()
                    time.sleep(2)
                    pipeline.start(config)
                    consecutive_errors = 0
                continue

            frame = np.asanyarray(color_frame.get_data())
            
            if frame is None or frame.size == 0:
                print("Invalid frame received")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    print("Too many errors, restarting pipeline...")
                    pipeline.stop()
                    time.sleep(2)
                    pipeline.start(config)
                    consecutive_errors = 0
                continue
            
            consecutive_errors = 0

            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
            
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                pass

        except RuntimeError as e:
            print(f"Frame timeout/error: {e}")
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                print("Too many errors, restarting pipeline...")
                try:
                    pipeline.stop()
                    time.sleep(2)
                    pipeline.start(config)
                    consecutive_errors = 0
                except Exception as restart_error:
                    print(f"Failed to restart pipeline: {restart_error}")
                    running = False
                    break
            time.sleep(0.1)
        except Exception as e:
            print(f"Capture thread error: {e}")
            import traceback
            traceback.print_exc()
            break
    
    pipeline.stop()
    print("RealSense pipeline stopped")

def send_thread():
    global running, frame_counter
    
    print("Send thread started")
    
    while running:
        try:
            frame = frame_queue.get(timeout=1)
            
            if frame is None:
                print("Skipping None frame")
                continue
            
            if frame.size == 0:
                print("Skipping empty frame")
                continue
            
            if len(frame.shape) != 3 or frame.shape[2] != 3:
                print(f"Skipping invalid frame shape: {frame.shape}")
                continue
            
            frame_counter += 1
            
            if frame_counter % FRAME_SKIP != 0:
                continue
            
            try:
                frame = cv2.resize(frame, (640, 480))
                
                if frame is None or frame.size == 0:
                    print("Frame corrupted after resize")
                    continue
                
                success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                
                if not success:
                    print("Failed to encode frame to JPEG")
                    continue
                
                if buffer is None or buffer.size == 0:
                    print("Empty buffer after encoding")
                    continue
                
                img_b64 = base64.b64encode(buffer).decode('utf-8')
                
                if not img_b64 or len(img_b64) < 100:
                    print(f"Invalid base64 string: length={len(img_b64)}")
                    continue
                
                if sio.connected:
                    sio.emit('inference_image', {'image': f'data:image/jpeg;base64,{img_b64}'})
                else:
                    print("Socket.IO not connected, skipping frame")
                    
            except cv2.error as e:
                print(f"OpenCV Error: {e}")
                continue
            except Exception as e:
                print(f"Frame processing error: {e}")
                continue
            
        except queue.Empty:
            continue
        except Exception as e:
            print(f"Send Error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)

    print("Send thread stopped")

# --- SOCKET.IO EVENTS ---
@sio.event
def connect():
    print("Socket.IO Connected")

@sio.event
def disconnect():
    print("Socket.IO Disconnected")

@sio.on('result_data')
def on_result(data):
    print(f"Server Result: {data['count']} people detected")

# --- MAIN ---
if __name__ == "__main__":
    try:
        print(f"Connecting to {SERVER_URL}...")
        try:
            sio.connect(SERVER_URL)
        except Exception as e:
            print(f"SocketIO Connection Warning: {e}")

        t_cap = threading.Thread(target=capture_thread, daemon=True)
        t_send = threading.Thread(target=send_thread, daemon=True)
        t_sens = threading.Thread(target=sensor_thread, daemon=True)
        
        t_cap.start()
        t_send.start()
        t_sens.start()
        
        print("System Running. Press Ctrl+C to stop.")
        
        while running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Stopping...")
        running = False
    finally:
        if sio.connected:
            sio.disconnect()
        print("System Shutdown")
