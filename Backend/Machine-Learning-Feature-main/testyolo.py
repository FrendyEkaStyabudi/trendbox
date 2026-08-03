import cv2
import numpy as np
import tensorflow as tf
tf.config.run_functions_eagerly(True)
tf.compat.v1.disable_eager_execution = False
import mediapipe as mp
import threading
import queue
import os
import math
from datetime import datetime
from collections import Counter
from tensorflow.keras.preprocessing.image import img_to_array

# --- LABEL FILTERING ---
ALLOWED_EMOTIONS = ['sad', 'happy', 'angry', 'fear', 'surprised']
ALLOWED_CLOTHES  = ['sweater', 'shorts', 'skirt', 'long_pants', 't-shirt', 'shirt', 'blouse', 'outer']
ALLOWED_HEAD     = ['hat', 'hair', 'hijab']  # English only

# --- HEAD LABEL TRANSLATION (YOLO -> English) ---
# YOLO head labels: rambut, hijab, topi
HEAD_TRANSLATION = {
    "rambut": "hair",
    "hijab": "hijab",
    "topi": "hat"
}

def translate_head(label: str) -> str:
    """Translate YOLO head label (ID) to English."""
    if not isinstance(label, str):
        return "-"
    label = label.lower()
    return HEAD_TRANSLATION.get(label, "-")


# --- LOAD YOLO SAFE ---
try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

# --- KONFIGURASI ---
TARGET_WIDTH = 400
YOLO_INTERVAL = 5

# --- LOAD MODELS ---
print("--- LOADING MODELS ---")
GLOBAL_MODELS = {}

GLOBAL_MODELS['mp_face'] = mp.solutions.face_detection.FaceDetection(
    min_detection_confidence=0.5
)

if os.path.exists('model_emotion2.h5'):
    GLOBAL_MODELS['emotion_model'] = tf.keras.models.load_model('model_emotion2.h5')
    print("✅ [SUCCESS] Emotion model loaded")
else:
    print("⚠️ [WARNING] model_emotion2.h5 not found, emotion disabled")

# YOLO
if HAS_YOLO:
    if os.path.exists("kepala.pt"):
        GLOBAL_MODELS['yolo_head'] = YOLO("kepala.pt")
        print("✅ YOLO head loaded")
    else:
        print("⚠ kepala.pt not found")
    if os.path.exists("pakaian.pt"):
        GLOBAL_MODELS['yolo_clothes'] = YOLO("pakaian.pt")
        print("✅ YOLO clothes loaded")
    else:
        print("⚠ pakaian.pt not found")
else:
    print("⚠ YOLO not installed")


print(GLOBAL_MODELS['yolo_clothes'].names)
