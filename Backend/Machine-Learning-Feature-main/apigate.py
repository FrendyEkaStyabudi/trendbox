# app.py
# Kode lengkap untuk aplikasi deteksi dan tracking emosi.
# Versi ini telah diperbaiki untuk mengatasi error dan meningkatkan performa.

# --- Import Library ---
import cv2
import numpy as np
import tensorflow as tf
import math
import threading
import time
import os
from flask import Flask, request, render_template, Response, jsonify, send_file
from flask_cors import CORS
from collections import deque, Counter
from tensorflow.keras.preprocessing.image import img_to_array
import mediapipe as mp
from datetime import datetime
import mysql.connector

# --- Konfigurasi Global ---
# Ganti detail ini sesuai dengan konfigurasi Cloud SQL Anda
DB_CONFIG = {
    'host': 'yamanote.proxy.rlwy.net',
    'user': 'root',
    'password': 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu',
    'database': 'railway',
    'port': '59862',
}

# Konstanta untuk model dan tracking
LABELS = ['angry', 'disgusted', 'fearful', 'happy', 'neutral', 'sad', 'surprised']
FILTERED_LABELS = ['happy', 'sad', 'angry', 'surprised', 'fearful']
CONFIDENCE_THRESHOLD = 0.5
HOLD_SECONDS = 5

# --- Class Definisi ---

class Person:
    """Mewakili satu orang yang di-track."""
    def __init__(self, personId, location):
        self.id = personId
        self.curLocation = location
        self.last_bbox = None
        self.trajectory = []
        self.emotion_history = []
        self.emotion_counts = Counter()
        self.color = tuple(np.random.randint(0, 256, 3).tolist())
        self.total_emotions = 0
        self.emotion_confidence = 0
        self.timestamp_history = []
        self.last_seen = datetime.now()
        self.saved = False
        self.trajectory_last_reset = datetime.now()
        self.trajectory_reset_interval = 5
        self.is_tracked_in_current_frame = True

    def addPointToTrajectory(self, location):
        self.trajectory.append(location)

    def addEmotion(self, emotion, conf):
        if emotion:
            self.emotion_history.append((emotion, conf))
            self.emotion_counts[emotion] += 1
            self.total_emotions += 1
            self.emotion_confidence += conf
            self.timestamp_history.append(datetime.now())

    def calculate_dominant_emotion(self):
        if not self.emotion_history:
            return None, None
        emotion_stats = {}
        for emotion, conf in self.emotion_history:
            if emotion not in emotion_stats:
                emotion_stats[emotion] = {'total_conf': 0.0, 'count': 0}
            emotion_stats[emotion]['total_conf'] += conf
            emotion_stats[emotion]['count'] += 1
        dominant_emotion = max(self.emotion_counts, key=self.emotion_counts.get)
        avg_conf_of_dominant = emotion_stats[dominant_emotion]['total_conf'] / emotion_stats[dominant_emotion]['count']
        return dominant_emotion, avg_conf_of_dominant

    def maybe_reset_trajectory(self):
        now = datetime.now()
        if (now - self.trajectory_last_reset).total_seconds() >= self.trajectory_reset_interval:
            self.trajectory.clear()
            self.trajectory_last_reset = now

class EmotionTracker:
    """Mengelola semua logika deteksi wajah, emosi, dan tracking."""
    def __init__(self):
        self.model = tf.keras.models.load_model('model_emotion2.h5')
        self.people = []
        self.mp_face = mp.solutions.face_detection
        self.detector = self.mp_face.FaceDetection(min_detection_confidence=0.5)
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.next_person_id = 0

    def calculate_iou(self, boxA, boxB):
        xA1, yA1, wA, hA = boxA
        xA2, yA2 = xA1 + wA, yA1 + hA
        xB1, yB1, wB, hB = boxB
        xB2, yB2 = xB1 + wB, yB1 + hB
        interX1 = max(xA1, xB1)
        interY1 = max(yA1, yB1)
        interX2 = min(xA2, xB2)
        interY2 = min(yA2, yB2)
        inter_area = max(0, interX2 - interX1) * max(0, interY2 - interY1)
        boxA_area = wA * hA
        boxB_area = wB * hB
        union_area = float(boxA_area + boxB_area - inter_area)
        return inter_area / union_area if union_area > 0 else 0.0

    def createPerson(self, bbox, center_coord):
        person = Person(self.next_person_id, center_coord)
        person.last_bbox = bbox
        self.people.append(person)
        self.next_person_id += 1
        return person

    def trackerHandle(self, face_data_list):
        now = datetime.now()
        for p in self.people:
            p.is_tracked_in_current_frame = False

        if not self.people:
            for data in face_data_list:
                self.createPerson(data['bbox'], data['coord'])
            return

        # PERBAIKAN 1: Mencegah error jika salah satu list kosong
        if not face_data_list:
            # Tidak ada deteksi baru, jadi kita hanya perlu update status orang lama
            pass
        else:
            iou_matrix = np.zeros((len(self.people), len(face_data_list)))
            for i, person in enumerate(self.people):
                for j, data in enumerate(face_data_list):
                    iou_matrix[i, j] = self.calculate_iou(person.last_bbox, data['bbox'])

            # Hanya proses jika matriks tidak kosong
            if iou_matrix.size > 0:
                while np.max(iou_matrix) > 0.3:
                    person_idx, detection_idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                    matched_data = face_data_list[detection_idx]
                    person = self.people[person_idx]
                    person.curLocation = matched_data['coord']
                    person.last_bbox = matched_data['bbox']
                    person.addPointToTrajectory(matched_data['coord'])
                    person.last_seen = now
                    person.is_tracked_in_current_frame = True
                    if matched_data['label'] and matched_data['conf'] >= CONFIDENCE_THRESHOLD:
                        person.addEmotion(matched_data['label'], matched_data['conf'])
                    iou_matrix[person_idx, :] = -1
                    iou_matrix[:, detection_idx] = -1

        # Logika untuk menghapus/menyimpan dan membuat orang baru
        active_people = []
        unmatched_detections = {i for i, data in enumerate(face_data_list) if not any(p.last_bbox == data['bbox'] and p.is_tracked_in_current_frame for p in self.people)}
        
        for person in self.people:
            if person.is_tracked_in_current_frame or (now - person.last_seen).total_seconds() <= HOLD_SECONDS:
                active_people.append(person)
            else:
                if not person.saved and person.total_emotions > 0:
                    self.save_person(person)
        self.people = active_people

        for idx in unmatched_detections:
            data = face_data_list[idx]
            self.createPerson(data['bbox'], data['coord'])

    def save_person(self, person):
        dominant_emotion, dominant_confidence = person.calculate_dominant_emotion()
        if dominant_emotion and person.timestamp_history:
            conn = None
            cursor = None
            try:
                # PERBAIKAN 2: Menggunakan pola try-finally untuk koneksi DB
                conn = mysql.connector.connect(**DB_CONFIG)
                cursor = conn.cursor()
                query = "INSERT INTO emotion_track (user_id, emotion, confidence, timestamp) VALUES (%s, %s, %s, %s)"
                values = (
                    f"user{person.id}",
                    dominant_emotion,
                    float(round(dominant_confidence, 3)),
                    person.timestamp_history[-1].strftime('%Y-%m-%d %H:%M:%S')
                )
                cursor.execute(query, values)
                conn.commit()
                print(f"[SQL INSERTED] Person {person.id} saved to DB.")
                person.saved = True
            except mysql.connector.Error as e:
                print(f"[SQL ERROR] {e}")
            finally:
                if cursor:
                    cursor.close()
                if conn and conn.is_connected():
                    conn.close()
        else:
            print(f"[SKIP SAVE] No dominant emotion or timestamp for person {person.id}")

    def detect_emotion(self, face_img):
        if face_img.size == 0: return None, 0
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (48, 48))
        array = img_to_array(resized)
        
        # PERBAIKAN 3: Menstabilkan input tensor untuk performa
        array = np.expand_dims(array, axis=0) / 255.0
        array = array.astype(np.float32) # Pastikan tipe data float32
        
        predictions = self.model.predict(array)[0]
        
        label_index = np.argmax(predictions)
        label = LABELS[label_index]
        confidence = predictions[label_index]
        return (label, float(confidence)) if label in FILTERED_LABELS else (None, 0)

    def process_frame(self, frame, frame_count):
        frame = cv2.resize(frame, (800, 600))
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.detector.process(rgb_frame)
        face_data_list = []
        if results.detections:
            for detection in results.detections:
                ih, iw, _ = frame.shape
                try:
                    box = detection.location_data.relative_bounding_box
                    x, y, w, h = int(box.xmin * iw), int(box.ymin * ih), int(box.width * iw), int(box.height * ih)
                except (ValueError, AttributeError):
                    continue # Skip jika data bounding box tidak valid
                x, y, w, h = max(0, x), max(0, y), min(iw - x, w), min(ih - y, h)
                face_img = frame[y:y+h, x:x+w]
                label, conf = self.detect_emotion(face_img)
                face_data_list.append({
                    'bbox': (x, y, w, h),
                    'coord': (x + w // 2, y + h // 2),
                    'label': label,
                    'conf': conf
                })
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                if label and conf >= CONFIDENCE_THRESHOLD:
                    cv2.putText(frame, f"{label} ({conf:.2f})", (x, y - 10), self.font, 0.7, (0, 255, 0), 2)
        
        self.trackerHandle(face_data_list)

        for person in self.people:
            if person.is_tracked_in_current_frame:
                person.maybe_reset_trajectory()
                for i in range(1, len(person.trajectory)):
                    cv2.line(frame, person.trajectory[i-1], person.trajectory[i], person.color, 2)
                x, y, w, h = person.last_bbox
                cv2.putText(frame, f"ID: {person.id}", (x, y + h + 20), self.font, 0.6, person.color, 2)
        
        active_count = sum(1 for p in self.people if p.is_tracked_in_current_frame)
        cv2.putText(frame, f"People Count: {active_count}", (10, 30), self.font, 1, (255, 0, 0), 2)
        return frame

# --- Inisialisasi Aplikasi Flask ---
app = Flask(__name__)
CORS(app)
video_capture = None
frame_queue = deque(maxlen=1)
frame_lock = threading.Lock()
emotion_tracker = EmotionTracker()

# --- Threads untuk Pemrosesan Video ---
def video_processing_thread():
    frame_count = 0
    while True:
        if not (video_capture and video_capture.isOpened()):
            time.sleep(0.1)
            continue
        success, frame = video_capture.read()
        if not success:
            time.sleep(0.5)
            continue
        if len(frame_queue) == 0:
            processed_frame = emotion_tracker.process_frame(frame, frame_count)
            with frame_lock:
                frame_queue.append(processed_frame)
        frame_count += 1
        time.sleep(0.01)

def gen_frames():
    while True:
        frame = None
        with frame_lock:
            if frame_queue:
                frame = frame_queue.popleft()
        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(1 / 30)

# --- Flask Routes (API Endpoints) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    global video_capture
    if video_capture is None or not video_capture.isOpened():
        video_capture = cv2.VideoCapture(0)
        if not video_capture.isOpened():
            return "Error: Could not open video source."
        threading.Thread(target=video_processing_thread, daemon=True).start()
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    people_copy = emotion_tracker.people[:]
    tracked_people = []
    for p in people_copy:
        if p.is_tracked_in_current_frame:
            emo, conf = p.calculate_dominant_emotion()
            tracked_people.append({
                "id": p.id,
                "emotion": emo.capitalize() if emo else "-",
                "confidence": f"{conf*100:.0f}%" if conf else "0%"
            })
    return jsonify({"people_count": len(tracked_people), "tracked_people": tracked_people})

@app.route('/inference_image', methods=['POST'])
def inference_image():
    try:
        np_arr = np.frombuffer(request.data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return "Invalid frame data", 400
        processed = emotion_tracker.process_frame(frame, 0)
        _, buffer = cv2.imencode('.jpg', processed)
        return Response(buffer.tobytes(), mimetype='image/jpeg')
    except Exception as e:
        print(f"Error in /inference_image: {e}")
        return "Server error", 500

@app.route('/download')
def download_csv():
    csv_path = "dominant_emotion.csv"
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True)
    return "File CSV tidak ditemukan. Data disimpan di database.", 404

# --- Jalankan Aplikasi ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)