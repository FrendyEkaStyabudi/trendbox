import cv2
import numpy as np
import tensorflow as tf
import math
from collections import Counter
from tensorflow.keras.preprocessing.image import img_to_array
import mediapipe as mp
import pandas as pd
from datetime import datetime
import os
import mysql.connector

DB_CONFIG = {
    'host': '34.128.100.191',       # Ganti sesuai IP Cloud SQL kamu
    'user': 'root',
    'password': 'admin',
    'database': 'emotion_trendbox'
}
LABELS = ['angry', 'disgusted', 'fearful', 'happy', 'neutral', 'sad', 'surprised']
FILTERED_LABELS = ['happy', 'sad', 'angry', 'surprised', 'fearful']
CONFIDENCE_THRESHOLD = 0.5
HOLD_SECONDS = 5

class Person:
    def __init__(self, personId, location):
        self.id = personId
        self.curLocation = location
        self.trajectory = []
        self.emotion_history = []
        self.emotion_counts = Counter()
        self.color = (255, 0, 0)
        self.total_emotions = 0
        self.emotion_confidence = 0
        self.timestamp_history = []
        self.last_seen = datetime.now()
        self.saved = False
        self.trajectory_last_reset = datetime.now()
        self.trajectory_reset_interval = 5  # detik


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
        if self.emotion_history:
            emotion_stats = {}
            for emotion, conf in self.emotion_history:
                if emotion not in emotion_stats:
                    emotion_stats[emotion] = [0.0, 0]
                emotion_stats[emotion][0] += conf
                emotion_stats[emotion][1] += 1

            emotion_scores = {}
            for emotion, (total_conf, count) in emotion_stats.items():
                avg_conf = total_conf / count
                score = count * avg_conf
                emotion_scores[emotion] = score

            dominant_emotion = max(emotion_scores, key=emotion_scores.get)
            dominant_conf = emotion_stats[dominant_emotion][0] / emotion_stats[dominant_emotion][1]  # total_conf / count
            return dominant_emotion, round(dominant_conf, 2)
        return None, None

    def get_average_confidence(self):
        if self.total_emotions > 0:
            return self.emotion_confidence / self.total_emotions
        return 0
    
    def maybe_reset_trajectory(self):
        now = datetime.now()
        if (now - self.trajectory_last_reset).total_seconds() >= self.trajectory_reset_interval:
            self.trajectory.clear()
            self.trajectory_last_reset = now



class EmotionTracker:
    def __init__(self):
        self.model = tf.keras.models.load_model('model_emotion2.h5')
        self.people = []
        self.mp_face = mp.solutions.face_detection
        # self.detector = self.mp_face.FaceDetection(min_detection_confidence=0.5)
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def detect_emotion(self, face_img):
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (48, 48))
        array = img_to_array(resized)
        array = np.expand_dims(array, axis=0) / 255.0
        predictions = self.model.predict(array, verbose=0)[0]
        label_index = np.argmax(predictions)
        label = LABELS[label_index]
        if label in FILTERED_LABELS:
            return label, predictions[label_index]
        return None, 0

    def calcDist(self, a, b):
        return math.sqrt((b[0] - a[0])**2 + (b[1] - a[1])**2)

    def createPerson(self, currentCoord):
        person = Person(len(self.people), currentCoord)
        self.people.append(person)

    def plotTrajectories(self, frame):
        for person in self.people:
            person.maybe_reset_trajectory()
            prev_point = None
            for i in person.trajectory:
                x, y = i
                if x <= 0 or y <= 0 or x > 10000 or y > 10000:
                    continue  # skip koordinat tidak wajar
                frame = cv2.circle(frame, (x, y), 3, person.color, cv2.FILLED)
                if prev_point:
                    frame = cv2.line(frame, prev_point, (x, y), person.color, 1)
                prev_point = (x, y)
        return frame

    def trackerHandle(self, face_data_list, frame):
        now = datetime.now()
        still_tracked_ids = set()
        curCoords = [data['coord'] for data in face_data_list]

        if self.people and curCoords:
            for person in self.people:
                dists = [self.calcDist(coord, person.curLocation) for coord in curCoords]
                if dists:
                    min_index = np.argmin(dists)
                    min_dist = dists[min_index]
                    if min_dist < 50:
                        matched_data = face_data_list[min_index]
                        person.curLocation = matched_data['coord']
                        person.addPointToTrajectory(matched_data['coord'])
                        person.last_seen = now
                        still_tracked_ids.add(person.id)
                        if matched_data['label'] and matched_data['conf'] >= CONFIDENCE_THRESHOLD:
                            person.addEmotion(matched_data['label'], matched_data['conf'])
                        face_data_list[min_index]['coord'] = (-999, -999)  # Mark matched

        for person in self.people[:]:
            time_since_last_seen = (now - person.last_seen).total_seconds()
            if person.id not in still_tracked_ids and time_since_last_seen > HOLD_SECONDS:
                if not person.saved and person.total_emotions > 0:
                    self.save_person(person)
                self.people.remove(person)

        for data in face_data_list:
            if data['coord'] != (-999, -999):
                self.createPerson(data['coord'])

    def save_person(self, person):
        dominant_emotion, dominant_confidence = person.calculate_dominant_emotion()
        print(f"[DEBUG] Saving person {person.id} - Dominant: {dominant_emotion}, Confidence: {dominant_confidence}")
        print(f"[DEBUG] Timestamps: {person.timestamp_history}")
    
        if dominant_emotion and person.timestamp_history:
            try:
                conn = mysql.connector.connect(**DB_CONFIG)
                cursor = conn.cursor()

                query = """
                INSERT INTO emotion_track (user_id, emotion, confidence, timestamp)
                VALUES (%s, %s, %s, %s)
                """
                values = (
                    f"user{person.id}",
                    dominant_emotion,
                    float(round(dominant_confidence, 3)),
                    person.timestamp_history[-1].strftime('%Y-%m-%d %H:%M:%S')
                )
                print(f"[DEBUG] Executing: {values}")
                cursor.execute(query, values)
                conn.commit()
                cursor.close()
                conn.close()
                print(f"[SQL INSERTED] Person {person.id} saved to DB.")
                person.saved = True
            except Exception as e:
                print("[SQL ERROR]", str(e))
        else:
            print(f"[SKIP] No dominant emotion or no timestamp")
            
    def save_remaining_people(self):
        for person in self.people:
            if not person.saved and person.total_emotions > 0:
                self.save_person(person)

    def process_frame(self, frame):
        frame = cv2.resize(frame, (800, 600))
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        with self.mp_face.FaceDetection(min_detection_confidence=0.5) as detector:
            results = detector.process(rgb_frame)


        face_data_list = []

        if results.detections:
            for detection in results.detections:
                ih, iw, _ = frame.shape
                box = detection.location_data.relative_bounding_box
                x, y, w, h = int(box.xmin * iw), int(box.ymin * ih), int(box.width * iw), int(box.height * ih)
                x, y, w, h = max(0, x), max(0, y), min(iw - x, w), min(ih - y, h)
                face_img = frame[y:y+h, x:x+w]

                label, conf = self.detect_emotion(face_img)
                if label and conf >= CONFIDENCE_THRESHOLD:
                    cv2.putText(frame, f"{label} ({conf:.2f})", (x, y - 10), self.font, 0.8, (0, 255, 0), 2)

                center_coord = (x + w // 2, y + h // 2)
                face_data_list.append({
                    'coord': center_coord,
                    'label': label,
                    'conf': conf
                })

                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        self.trackerHandle(face_data_list, frame)
        frame = self.plotTrajectories(frame)
        cv2.putText(frame, f"People Count: {len(self.people)}", (10, 30), self.font, 1, (255, 0, 0), 2)
        return frame
