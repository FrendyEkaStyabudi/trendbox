import cv2
import numpy as np
import tensorflow as tf
import mediapipe as mp
import threading
import queue
import os
import math
from datetime import datetime
from collections import Counter
from tensorflow.keras.preprocessing.image import img_to_array
import csv
import json
import base64

# Runtime tuning. Values can be overridden per Google Cloud service without
# rebuilding the image.
TARGET_WIDTH = int(os.getenv('INFERENCE_WIDTH', '416'))
YOLO_INTERVAL = max(1, int(os.getenv('YOLO_INTERVAL', '5')))
YOLO_IMGSZ = int(os.getenv('YOLO_IMGSZ', '416'))
YOLO_DEVICE = os.getenv('YOLO_DEVICE', 'auto').strip().lower()
YOLO_HALF = os.getenv('YOLO_HALF', 'false').lower() in ('1', 'true', 'yes')
TFLITE_THREADS = max(1, int(os.getenv('TFLITE_THREADS', str(min(4, os.cpu_count() or 1)))))

# --- LABEL FILTERING ---
# 1. KAMUS MODEL (WAJIB 7 & URUT ABJAD - Jangan Diubah)
LABELS = ['angry', 'disgusted', 'fearful', 'happy', 'neutral', 'sad', 'surprised']

# 2. DAFTAR YANG MAU DIPAKAI (Filter)
# Hapus neutral dan disgusted dari sini
TARGET_EMOTIONS = ['angry', 'fear', 'happy', 'sad', 'surprised']
DISPLAY_EMOTIONS = TARGET_EMOTIONS
EMOTION_DEBUG_EVERY_FRAMES = 30
LOG_HOOK = None


def emit_log(level, message, sid=None):
    if LOG_HOOK:
        LOG_HOOK(level, message, sid=sid)
    else:
        print(f"[{level.upper()}] {message}")

# Head & Clothes
ALLOWED_CLOTHES = ['sweater', 'shorts', 'skirt', 'long_pants', 't-shirt', 'shirt', 'blouse', 'outer']
ALLOWED_HEAD = ['hat', 'hair', 'hijab']  # English

# --- HEAD LABEL TRANSLATION (YOLO -> English) ---
HEAD_TRANSLATION = {
    "rambut": "hair",
    "hijab": "hijab",
    "topi": "hat"
}

def translate_head(label: str) -> str | None:
    if not isinstance(label, str):
        return None
    return HEAD_TRANSLATION.get(label.lower(), None)

# --- CLOTHES LABEL TRANSLATION (YOLO -> English) ---
CLOTHES_TRANSLATION = {
    "celana panjang": "long_pants",
    "celana pendek": "shorts",
    "gaun": "dress",
    "hijab": "hijab",
    "kaos": "t-shirt",
    "kemeja": "shirt",
    "outer": "outer",
    "rok": "skirt",
    "sweater": "sweater",
    "tas": "bag",
    "topi": "hat"
}

def translate_clothes(label: str) -> str | None:
    if not isinstance(label, str):
        return None
    return CLOTHES_TRANSLATION.get(label.lower(), None)


# --- LOAD YOLO SAFE ---
try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

# --- KONFIGURASI ---
YOLO_CONFIDENCE = 0.35
SAME_LABEL_IOU_THRESHOLD = 0.45

# --- LOAD MODELS ---
print("--- LOADING MODELS ---")
GLOBAL_MODELS = {}

class TFLiteEmotionModel:
    def __init__(self, model_path):
        self.interpreter = tf.lite.Interpreter(
            model_path=model_path,
            num_threads=TFLITE_THREADS,
        )
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self.lock = threading.Lock()

    def __call__(self, face_roi, training=False):
        input_detail = self.input_details[0]
        input_data = np.ascontiguousarray(face_roi.astype(input_detail['dtype']))
        with self.lock:
            self.interpreter.set_tensor(input_detail['index'], input_data)
            self.interpreter.invoke()
            output = self.interpreter.get_tensor(self.output_details[0]['index'])
            return np.array(output, copy=True)

if os.path.exists('model_emotion2.h5'):
    GLOBAL_MODELS['emotion_model'] = tf.keras.models.load_model('model_emotion2.h5')
    print("? [SUCCESS] Emotion H5 model loaded")
elif os.path.exists('model_emotion2.tflite'):
    GLOBAL_MODELS['emotion_model'] = TFLiteEmotionModel('model_emotion2.tflite')
    print("? [SUCCESS] Emotion TFLite model loaded")
else:
    print("?? [WARNING] model_emotion2.h5/.tflite not found, emotion disabled")

# YOLO
if HAS_YOLO:
    if os.path.exists("kepala.pt"):
        GLOBAL_MODELS['yolo_head'] = YOLO("kepala.pt")
        print("âœ… YOLO head loaded")
    else:
        print("âš  kepala.pt not found")

    if os.path.exists("pakaian.pt"):
        GLOBAL_MODELS['yolo_clothes'] = YOLO("pakaian.pt")
        print("âœ… YOLO clothes loaded")
    else:
        print("âš  pakaian.pt not found")
else:
    print("âš  YOLO not installed")


# --- DATABASE ---
try:
    from mysql.connector import pooling
    DB_CONFIG = {
        'user': os.getenv('DB_USER', 'trendbox-app'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_DATABASE', os.getenv('DB_NAME', 'trendbox')),
        'pool_name': "mypool",
        'pool_size': 3,
        'connect_timeout': 10
    }
    instance_connection_name = os.getenv('INSTANCE_CONNECTION_NAME', '').strip()
    if instance_connection_name:
        DB_CONFIG['unix_socket'] = f"/cloudsql/{instance_connection_name}"
    else:
        DB_CONFIG['host'] = os.getenv('DB_HOST', '127.0.0.1')
        DB_CONFIG['port'] = int(os.getenv('DB_PORT', '3306'))
    db_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
    print("âœ… Database connected")
except Exception as e:
    db_pool = None
    print(f"âš  DB Offline: {e}")


# --- IOU ---
def get_iou(boxA, boxB):
    xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
    xB, yB = min(boxA[2], boxB[2]), min(boxA[3], boxB[3])
    interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
    if interArea == 0:
        return 0.0
    boxAArea = (boxA[2] - boxA[0] + 1) * (boxA[3] - boxA[1] + 1)
    boxBArea = (boxB[2] - boxB[0] + 1) * (boxB[3] - boxB[1] + 1)
    return interArea / float(boxAArea + boxBArea - interArea)


def suppress_same_label_overlaps(detections, iou_threshold=SAME_LABEL_IOU_THRESHOLD):
    kept = []
    for detection in sorted(detections, key=lambda item: item.get('conf') or 0.0, reverse=True):
        overlaps_same_label = any(
            detection['label'] == existing['label'] and get_iou(detection['box'], existing['box']) >= iou_threshold
            for existing in kept
        )
        if not overlaps_same_label:
            kept.append(detection)
    return kept


UPPER_CLOTHING_LABELS = {'t-shirt', 'shirt', 'outer', 'sweater', 'blouse', 'kaos', 'kemeja'}
LOWER_CLOTHING_LABELS = {'long_pants', 'shorts', 'skirt', 'celana panjang', 'celana pendek', 'rok'}
HIJAB_CONFIDENCE_THRESHOLD = 0.78
HAIR_CONFIDENCE_THRESHOLD = 0.25

def keep_best_detection(detections):
    if not detections:
        return []
    return [max(detections, key=lambda item: item.get('conf') or 0.0)]

def keep_best_per_category(detections):
    if not detections:
        return []
    best_by_cat = {}
    for d in detections:
        label = d['label'].lower()
        if label in UPPER_CLOTHING_LABELS:
            cat = 'upper'
        elif label in LOWER_CLOTHING_LABELS:
            cat = 'lower'
        else:
            cat = label
        if cat not in best_by_cat or (d.get('conf') or 0.0) > (best_by_cat[cat].get('conf') or 0.0):
            best_by_cat[cat] = d
    return list(best_by_cat.values())


class Person:
    def __init__(self, pid, loc):
        self.id = pid
        self.curLocation = loc
        self.emotion_history = []
        self.last_seen = datetime.now()
        self.saved = False
        self.head_data = {'label': '-', 'conf': 0.0}
        self.cloth_data = {'label': '-', 'conf': 0.0}
        self.cloth_upper = {'label': '-', 'conf': 0.0}
        self.cloth_lower = {'label': '-', 'conf': 0.0}
        self.color = tuple(np.random.randint(50, 255, 3).tolist())

    def update(self, loc):
        self.curLocation = loc
        self.last_seen = datetime.now()

    def get_dominant_emotion(self):
        """
        Hanya menghitung emosi yang ada di TARGET_EMOTIONS.
        Jika isinya cuma neutral/disgusted, dia akan return None.
        """
        if not self.emotion_history:
            return None, 0.0

        # Filter: Hanya ambil data yang ada di TARGET_EMOTIONS
        # 'fearful' dianggap 'fear'
        valid_emotions = []
        for e in self.emotion_history:
            emo = e[0]
            if emo == 'fearful': emo = 'fear' # Normalisasi
            
            if emo in TARGET_EMOTIONS:
                valid_emotions.append(emo)

        # Jika setelah difilter kosong (isinya neutral semua), return None
        if not valid_emotions:
            return None, 0.0

        # Hitung yang terbanyak dari sisa yang valid
        label, count = Counter(valid_emotions).most_common(1)[0]
        return label, float(count)

    def get_display_emotion(self):
        if not self.emotion_history:
            return None, 0.0

        valid_emotions = []
        confidence_by_emotion = {}
        for emotion, confidence in self.emotion_history:
            if emotion == 'fearful':
                emotion = 'fear'
            if emotion in DISPLAY_EMOTIONS:
                valid_emotions.append(emotion)
                confidence_by_emotion.setdefault(emotion, []).append(float(confidence))

        if not valid_emotions:
            return None, 0.0

        label, _count = Counter(valid_emotions).most_common(1)[0]
        confidences = confidence_by_emotion.get(label, [0.0])
        return label, sum(confidences) / len(confidences)


class EmotionTracker:
    def __init__(self, session_id):
        self.session_id = session_id
        self.people = []
        self.next_id = 1
        self.frame_count = 0
        self.running = True
        self.db_queue = queue.Queue()
        self.cache_heads = []
        self.cache_clothes = []
        self.csv_filename = "log_detection_result.csv"
        
        # CREATE MEDIAPIPE INSTANCE PER SESSION
        self.mp_face = mp.solutions.face_detection.FaceDetection(
            min_detection_confidence=0.5
        )

        self.config = {
            'emotion': True,
            'head': True,
            'clothing': True,
            'db_save': True,
            # Saving a JPEG + Base64 payload on every frame is intentionally
            # opt-in; persistent Cloud storage/logging must not block inference.
            'save_csv': False
        }

        if db_pool:
            threading.Thread(target=self._db_loop, daemon=True).start()

        print(f"[EmotionTracker] Initialized for session {self.session_id}")

    def update_settings(self, new_config: dict):
        # Deteksi jika CSV logging baru saja diaktifkan
        turning_on = new_config.get('save_csv') is True
        currently_off = self.config.get('save_csv') is False
        
        self.config.update(new_config)
        print(f"[{self.session_id}] Config Updated: {self.config}")
        
        # Reset CSV file jika baru diaktifkan
        if currently_off and turning_on:
            self._reset_csv_file()

    def _reset_csv_file(self):
        try:
            with open(self.csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'SessionID', 'Person_Count', 'Metadata_JSON', 'Image_Base64'])
            print(f"âœ… [CSV] File RESET & STARTED: {self.csv_filename}")
        except Exception as e:
            print(f"âš  [CSV Reset Error] {e}")

    def _db_loop(self):
        while self.running:
            try:
                packet = self.db_queue.get(timeout=1)
            except queue.Empty:
                continue

            # TAMBAHKAN LOGGING
            emit_log("info", f"DB queue processing packet for {packet['uid']}", sid=self.session_id)
            emit_log(
                "info",
                f"Emotion={packet['emotion']} Head={packet['head_label']} Clothing={packet['cloth_label']}",
                sid=self.session_id,
            )

            try:
                conn = db_pool.get_connection()
                cur = conn.cursor()

                # Insert Emotion HANYA jika ada dan allowed
                if packet['emotion'] is not None:
                    cur.execute(
                        """
                        INSERT INTO emotion_track (user_id, emotion, confidence, timestamp)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (packet['uid'], packet['emotion'], 0.9, packet['timestamp'])
                    )
                    emit_log("info", f"Emotion inserted: {packet['emotion']}", sid=self.session_id)

                # Insert Head HANYA jika ada dan allowed
                if packet['head_label'] is not None:
                    cur.execute(
                        """
                        INSERT INTO head_track (label, confidence, timestamp, source)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (packet['head_label'], packet['head_conf'],
                         packet['timestamp'], packet['uid'])
                    )
                    emit_log("info", f"Head inserted: {packet['head_label']}", sid=self.session_id)

                # Insert Clothing HANYA jika ada dan allowed
                if packet.get('clothing_items'):
                    for c_label, c_conf in packet['clothing_items']:
                        cur.execute(
                            """
                            INSERT INTO clothing_track (label, confidence, timestamp, source)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (c_label, c_conf, packet['timestamp'], packet['uid'])
                        )
                        emit_log("info", f"Clothing inserted: {c_label}", sid=self.session_id)
                elif packet.get('cloth_label') is not None:
                    cur.execute(
                        """
                        INSERT INTO clothing_track (label, confidence, timestamp, source)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (packet['cloth_label'], packet['cloth_conf'],
                         packet['timestamp'], packet['uid'])
                    )
                    emit_log("info", f"Clothing inserted: {packet['cloth_label']}", sid=self.session_id)

                conn.commit()
                conn.close()
                emit_log("info", f"DB saved for {packet['uid']}", sid=self.session_id)
            except Exception as e:
                emit_log("error", f"DB error: {e}", sid=self.session_id)
                import traceback
                traceback.print_exc()
            finally:
                self.db_queue.task_done()

    def stop(self):
        self.running = False

    def save_person(self, p: Person):
        if not db_pool or not self.config.get('db_save', True):
            print(f"⚠️ [DB] Skipping save - db_pool={db_pool is not None}, db_save={self.config.get('db_save')}")
            return

        dom, conf = p.get_dominant_emotion()

        # LOGGING
        print(f"💾 [SAVE] Attempting to save Person ID {p.id}")
        print(f"   - Emotion history: {p.emotion_history}")
        print(f"   - Dominant: {dom}")
        print(f"   - Head: {p.head_data}")
        print(f"   - Clothes Upper: {p.cloth_upper}")
        print(f"   - Clothes Lower: {p.cloth_lower}")

        # Siapkan nilai aman: None bila fitur dimatikan / tidak allowed / tidak ada
        if self.config.get('head', True):
            head_label = p.head_data['label'] if p.head_data['label'] in ALLOWED_HEAD else None
            head_conf  = float(p.head_data['conf']) if head_label is not None else None
        else:
            head_label = None
            head_conf = None

        clothing_items = []
        if self.config.get('clothing', True):
            if p.cloth_upper['label'] in ALLOWED_CLOTHES:
                clothing_items.append((p.cloth_upper['label'], float(p.cloth_upper['conf'])))
            if p.cloth_lower['label'] in ALLOWED_CLOTHES and p.cloth_lower['label'] != p.cloth_upper['label']:
                clothing_items.append((p.cloth_lower['label'], float(p.cloth_lower['conf'])))
            if not clothing_items and p.cloth_data['label'] in ALLOWED_CLOTHES:
                clothing_items.append((p.cloth_data['label'], float(p.cloth_data['conf'])))

            cloth_label = clothing_items[0][0] if clothing_items else None
            cloth_conf = clothing_items[0][1] if clothing_items else None
        else:
            cloth_label = None
            cloth_conf = None

        if self.config.get('emotion', True) and dom is not None:
            emotion_label = dom
        else:
            emotion_label = None

        data_packet = {
            'uid': f"{self.session_id}_{p.id}",
            'timestamp': datetime.now(),
            'emotion': emotion_label,
            'head_label': head_label,
            'head_conf': head_conf,
            'cloth_label': cloth_label,
            'cloth_conf': cloth_conf,
            'clothing_items': clothing_items
        }

        if self.config.get('db_save', True):
            print(f"   📦 Queuing packet: {data_packet}")
            self.db_queue.put(data_packet)
        p.saved = True

    def get_people_json(self):
        result = []
        now = datetime.now()
        for p in self.people:
            dom, conf = p.get_display_emotion()
            if not self.config.get('emotion', True):
                dom, conf = '-', 0.0
            head_label = p.head_data['label'] if self.config.get('head', True) else '-'
            cloth_label = p.cloth_data['label'] if self.config.get('clothing', True) else '-'
            
            # Calculate duration in seconds
            duration_seconds = (now - p.last_seen).total_seconds()
            
            result.append({
                "id": p.id,
                "emotion": dom if dom is not None else "-",
                "confidence": conf if conf else 0.0,  # âœ… ADD THIS
                "head": head_label,
                "clothes": cloth_label,
                "duration": duration_seconds  # âœ… CHANGE TO NUMBER
            })
        return result
    
    def _save_log_csv(self, frame, people_json):
        try:
            # Encode gambar ke Base64 (Quality 50%)
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
            img_b64 = base64.b64encode(buffer).decode('utf-8')
            img_data_str = "data:image/jpeg;base64," + img_b64

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            metadata_str = json.dumps(people_json)
            person_count = len(people_json)

            # Append ke file
            with open(self.csv_filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, self.session_id, person_count, metadata_str, img_data_str])
                
            print(f"âœ… [CSV] Logged: {person_count} people at {timestamp}")
                
        except Exception as e:
            print(f"âŒ [CSV Log Error] {e}")

    def process_frame(self, frame):
        # VALIDASI FRAME - Cek frame tidak None dan tidak kosong
        if frame is None:
            print("âš ï¸ [Frame Validation] Received None frame")
            return np.zeros((480, 640, 3), dtype=np.uint8)  # Return blank frame
        
        if frame.size == 0:
            print("âš ï¸ [Frame Validation] Received empty frame")
            return np.zeros((480, 640, 3), dtype=np.uint8)  # Return blank frame
        
        if len(frame.shape) != 3 or frame.shape[2] != 3:
            print(f"âš ï¸ [Frame Validation] Invalid frame shape: {frame.shape}")
            return np.zeros((480, 640, 3), dtype=np.uint8)  # Return blank frame

        self.frame_count += 1
        h, w = frame.shape[:2]
        
        # Validasi dimensi frame
        if h == 0 or w == 0:
            print(f"âš ï¸ [Frame Validation] Invalid dimensions: {w}x{h}")
            return np.zeros((480, 640, 3), dtype=np.uint8)
        
        ratio = TARGET_WIDTH / w
        target_h = int(h * ratio)
        
        try:
            frame = cv2.resize(frame, (TARGET_WIDTH, target_h))
        except Exception as e:
            print(f"❌ [Resize Error] {e}")
            return np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Konversi ke RGB dengan error handling
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print(f"⚠️ [Color Conversion Error] {e}")
            return frame

        emotion_enabled = self.config.get('emotion', True)
        head_enabled = self.config.get('head', True)
        clothing_enabled = self.config.get('clothing', True)

        if not head_enabled:
            self.cache_heads = []
        if not clothing_enabled:
            self.cache_clothes = []

        # Stagger YOLO models across different frames to eliminate frame freezes
        should_run_head = head_enabled and ('yolo_head' in GLOBAL_MODELS) and (self.frame_count % YOLO_INTERVAL == 1)
        should_run_clothes = clothing_enabled and ('yolo_clothes' in GLOBAL_MODELS) and (self.frame_count % YOLO_INTERVAL == 3)

        # HEAD
        if should_run_head:
            self.cache_heads = []
            try:
                head_detections = []
                yolo_args = {
                    'verbose': False,
                    'conf': YOLO_CONFIDENCE,
                    'iou': SAME_LABEL_IOU_THRESHOLD,
                    'imgsz': YOLO_IMGSZ,
                }
                if YOLO_DEVICE != 'auto':
                    yolo_args['device'] = YOLO_DEVICE
                if YOLO_HALF:
                    yolo_args['half'] = True
                res = GLOBAL_MODELS['yolo_head'](frame, **yolo_args)
                for r in res:
                    for box in r.boxes:
                        raw_label = GLOBAL_MODELS['yolo_head'].names[int(box.cls[0])]
                        trans_label = translate_head(raw_label)

                        if trans_label in ALLOWED_HEAD:
                            conf_val = float(box.conf[0])
                            # Threshold khusus: Hijab dinaikkan ke 0.78 (78%), Hair diturunkan ke 0.25 (25%)
                            if trans_label == 'hijab' and conf_val < HIJAB_CONFIDENCE_THRESHOLD:
                                continue
                            if trans_label == 'hair' and conf_val < HAIR_CONFIDENCE_THRESHOLD:
                                continue
                            head_detections.append({
                                'box': box.xyxy[0].cpu().numpy().astype(int),
                                'label': trans_label,
                                'conf': conf_val
                            })
                self.cache_heads = keep_best_detection(head_detections)
            except Exception as e:
                print(f"⚠️ [YOLO Head Error] {e}")

        # CLOTHING
        if should_run_clothes:
            self.cache_clothes = []
            try:
                clothing_detections = []
                yolo_args = {
                    'verbose': False,
                    'conf': YOLO_CONFIDENCE,
                    'iou': SAME_LABEL_IOU_THRESHOLD,
                    'imgsz': YOLO_IMGSZ,
                }
                if YOLO_DEVICE != 'auto':
                    yolo_args['device'] = YOLO_DEVICE
                if YOLO_HALF:
                    yolo_args['half'] = True
                res = GLOBAL_MODELS['yolo_clothes'](frame, **yolo_args)
                for r in res:
                    for box in r.boxes:
                        raw_label = GLOBAL_MODELS['yolo_clothes'].names[int(box.cls[0])]
                        trans_label = translate_clothes(raw_label)

                        if trans_label in ALLOWED_CLOTHES:
                            clothing_detections.append({
                                'box': box.xyxy[0].cpu().numpy().astype(int),
                                'label': trans_label,
                                'conf': float(box.conf[0])
                            })
                # Menggunakan keep_best_per_category agar Atasan dan Bawahan MUNCUL BERSAMAAN
                self.cache_clothes = keep_best_per_category(clothing_detections)
            except Exception as e:
                    print(f"⚠️ [YOLO Clothes Error] {e}")

        # DRAW YOLO VISUAL
        if head_enabled:
            for hbox in self.cache_heads:
                cv2.rectangle(frame, (hbox['box'][0], hbox['box'][1]),
                              (hbox['box'][2], hbox['box'][3]), (0, 0, 255), 2)
                cv2.putText(frame, hbox['label'], (hbox['box'][0], max(15, hbox['box'][1] - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)

        if clothing_enabled:
            for cbox in self.cache_clothes:
                cv2.rectangle(frame, (cbox['box'][0], cbox['box'][1]),
                              (cbox['box'][2], cbox['box'][3]), (0, 255, 255), 2)
                cv2.putText(frame, cbox['label'], (cbox['box'][0], max(15, cbox['box'][1] - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 2)

        active_ids = set()
        faces_drawn = 0
        
        # MEDIAPIPE FACE DETECTION dengan error handling
        try:
            if rgb is None or rgb.size == 0:
                print("âš ï¸ [MediaPipe] Invalid RGB frame")
                return frame
            
            results = self.mp_face.process(rgb)
            
        except Exception as e:
            # Skip frame jika ada timestamp mismatch
            error_msg = str(e)
            if "timestamp mismatch" in error_msg.lower():
                print(f"âš ï¸ [MediaPipe] Timestamp mismatch - skipping frame")
            else:
                print(f"âŒ [MediaPipe Error] {error_msg[:100]}")
            
            # Return frame tanpa face detection untuk frame ini
            return frame

        should_log_emotion_debug = self.frame_count % EMOTION_DEBUG_EVERY_FRAMES == 0
        if should_log_emotion_debug:
            face_count = len(results.detections) if results.detections else 0
            emit_log(
                "debug",
                f"[EmotionDebug] frame={self.frame_count} faces={face_count} "
                f"emotion_enabled={emotion_enabled} model_loaded={'emotion_model' in GLOBAL_MODELS}",
                sid=self.session_id,
            )

        if results.detections:
            for det in results.detections:
                bbox = det.location_data.relative_bounding_box
                x = int(bbox.xmin * TARGET_WIDTH)
                y = int(bbox.ymin * target_h)
                w_box = int(bbox.width * TARGET_WIDTH)
                h_box = int(bbox.height * target_h)

                if w_box < 10 or h_box < 10:
                    continue

                x = max(0, x)
                y = max(0, y)

                # EMOTION (MODIFIED)
# ... (Bagian atas sama) ...

                # EMOTION (MODIFIED WITH LOGIC HACK)
                raw_label = None
                confidence = 0.0
                if emotion_enabled and 'emotion_model' in GLOBAL_MODELS:
                    try:
                        face_roi = frame[y:y + h_box, x:x + w_box]
                        if face_roi.size > 0:
                            # Preprocessing
                            face_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                            face_roi = cv2.resize(face_roi, (48, 48)) / 255.0
                            face_roi = np.expand_dims(img_to_array(face_roi), axis=0)
                            
                            # Prediksi Raw
                            preds = GLOBAL_MODELS['emotion_model'](face_roi, training=False)[0]
                            idx = np.argmax(preds)
                            
                            raw_label = LABELS[idx]
                            confidence = float(preds[idx]) # Ambil tingkat keyakinan (0.0 - 1.0)

                            # --- [MODIFIKASI DI SINI] ---
                            # ANTI-BAPER LOGIC:
                            # Jika terdeteksi 'sad' tapi confidence < 0.60 (60%), paksa jadi 'neutral'.
                            # Angka 0.60 bisa kamu naik turunkan sesuai kondisi cahaya.
                            if raw_label == 'sad' and confidence < 0.40:
                                raw_label = 'neutral'
                            # ----------------------------

                            # Mapping fearful -> fear
                            if raw_label == "fearful":
                                raw_label = "fear"

                            if should_log_emotion_debug:
                                top_scores = sorted(
                                    zip(LABELS, [float(score) for score in preds]),
                                    key=lambda item: item[1],
                                    reverse=True,
                                )[:3]
                                top_text = ", ".join(f"{label}:{score:.2f}" for label, score in top_scores)
                                emit_log(
                                    "debug",
                                    f"[EmotionDebug] raw={raw_label} confidence={confidence:.2f} top={top_text}",
                                    sid=self.session_id,
                                )

                    except Exception as e:
                        emit_log("error", f"Emotion error: {e}", sid=self.session_id)
                elif should_log_emotion_debug:
                    emit_log(
                        "debug",
                        f"[EmotionDebug] skipped emotion inference: "
                        f"emotion_enabled={emotion_enabled}, model_loaded={'emotion_model' in GLOBAL_MODELS}",
                        sid=self.session_id,
                    )


                center = (x + w_box // 2, y + h_box // 2)
                matched = None
                min_dist = 100

                for p in self.people:
                    dist = math.dist(p.curLocation, center)
                    if dist < min_dist:
                        min_dist = dist
                        matched = p

                if not matched:
                    matched = Person(self.next_id, center)
                    self.people.append(matched)
                    self.next_id += 1

                matched.update(center)
                
                # UPDATE HISTORY (Masukkan SEMUA, biar Person tau dia sedang dideteksi)
                if raw_label is not None:
                    matched.emotion_history.append((raw_label, confidence))
                active_ids.add(matched.id)

                # ATTRIBUTE MATCHING
                face_rect = [x, y, x + w_box, y + h_box]

                # HEAD
                if head_enabled:
                    for hbox in self.cache_heads:
                        if get_iou(face_rect, hbox['box']) > 0:
                            matched.head_data = hbox

                # CLOTHES (Matching Atasan & Bawahan Bersamaan)
                if clothing_enabled:
                    fx, fy = center
                    best_upper = None
                    min_upper_dist = 1000
                    best_lower = None
                    min_lower_dist = 1000

                    for cbox in self.cache_clothes:
                        cx = (cbox['box'][0] + cbox['box'][2]) // 2
                        cy = (cbox['box'][1] + cbox['box'][3]) // 2
                        label_lower = cbox['label'].lower()

                        if cy > fy and abs(cx - fx) < w_box * 2.0:
                            v_dist = cy - fy
                            if label_lower in UPPER_CLOTHING_LABELS:
                                if v_dist < min_upper_dist:
                                    min_upper_dist = v_dist
                                    best_upper = cbox
                            elif label_lower in LOWER_CLOTHING_LABELS:
                                if v_dist < min_lower_dist:
                                    min_lower_dist = v_dist
                                    best_lower = cbox
                            else:
                                if v_dist < min_upper_dist:
                                    min_upper_dist = v_dist
                                    best_upper = cbox

                    if best_upper is not None:
                        matched.cloth_upper = best_upper
                        matched.cloth_data = best_upper
                    if best_lower is not None:
                        matched.cloth_lower = best_lower
                        if best_upper is None:
                            matched.cloth_data = best_lower

                # DRAW PERSON BOX
                faces_drawn += 1
                cv2.rectangle(frame, (x, y), (x + w_box, y + h_box), matched.color, 3)

                # TEXT EMOTION (LOGIKA TAMPILAN)
                display_text = "-"
                
                if emotion_enabled and raw_label in DISPLAY_EMOTIONS:
                    display_text = raw_label

                cv2.putText(
                    frame,
                    f"ID:{matched.id} {display_text}",
                    (x, y - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    matched.color,
                    2
                )

                head_label = matched.head_data['label'] if head_enabled else '-'
                
                clothes_parts = []
                if clothing_enabled:
                    if matched.cloth_upper['label'] != '-':
                        clothes_parts.append(matched.cloth_upper['label'])
                    if matched.cloth_lower['label'] != '-':
                        clothes_parts.append(matched.cloth_lower['label'])
                    if not clothes_parts and matched.cloth_data['label'] != '-':
                        clothes_parts.append(matched.cloth_data['label'])
                
                attr_parts = []
                if head_enabled and head_label != '-':
                    attr_parts.append(f"H:{head_label}")
                if clothing_enabled and cloth_label != '-':
                    attr_parts.append(f"C:{cloth_label}")
                
                if attr_parts:
                    attr_txt = "   ".join(attr_parts)
                    cv2.putText(
                        frame,
                        attr_txt,
                        (x, y + h_box + 15),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        (255, 255, 255),
                        1
                    )

        # Cleanup
        now = datetime.now()
        # Gunakan list() untuk membuat shallow copy agar aman saat iterasi
        people_snapshot = list(self.people)
        
        for p in people_snapshot:
            time_elapsed = (now - p.last_seen).total_seconds()
            
            if p.id not in active_ids:
                if time_elapsed > 3:
                    # Save to database if not yet saved
                    if not p.saved:
                        try:
                            self.save_person(p)
                        except Exception as e:
                            print(f"âŒ [Save Person Error] {e}")
                    
                    # Safe remove dengan validasi
                    try:
                        # Double-check person masih ada di list original
                        if p in self.people:
                            self.people.remove(p)
                            print(f"âœ… Person {p.id} removed from tracking")
                        else:
                            print(f"âš ï¸ Person {p.id} already removed by another thread")
                    except ValueError as e:
                        # Catch jika sudah di-remove oleh thread lain (race condition)
                        print(f"âš ï¸ [Cleanup] Person {p.id} removal failed: {e}")
                    except Exception as e:
                        print(f"âŒ [Cleanup Error] {e}")

        # CSV LOGGING
        if self.config.get('save_csv', False):
            current_people_data = self.get_people_json()
            if len(current_people_data) > 0:
                self._save_log_csv(frame, current_people_data)

        return frame
