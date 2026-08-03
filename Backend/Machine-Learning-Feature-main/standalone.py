import cv2
import numpy as np
import mediapipe as mp
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array

# --- KONFIGURASI ---
MODEL_PATH = 'model_emotion2.h5'
IMAGE_SIZE = (48, 48)

# PENTING: Urutan label harus sama persis dengan urutan alfabetis folder training
LABELS = ['angry', 'disgusted', 'fearful', 'happy', 'neutral', 'sad', 'surprised']

# --- LOAD MODEL ---
print(f"Loading model dari {MODEL_PATH}...")
try:
    model = load_model(MODEL_PATH)
    print("Model berhasil dimuat!")
except Exception as e:
    print(f"Error loading model: {e}")
    exit()

# --- INISIALISASI MEDIAPIPE (DETEKSI WAJAH) ---
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils
face_detection = mp_face_detection.FaceDetection(min_detection_confidence=0.5)

# --- FUNGSI PREPROCESSING ---
def preprocess_input(face_image):
    # 1. Ubah ke Grayscale (Sesuai training)
    face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
    
    # 2. Resize ke 48x48
    face_image = cv2.resize(face_image, IMAGE_SIZE)
    
    # 3. Normalisasi (0-1)
    face_image = face_image.astype("float") / 255.0
    
    # 4. Ubah ke array dan tambah dimensi
    # Input model butuh (Batch, Height, Width, Channel) -> (1, 48, 48, 1)
    face_image = img_to_array(face_image)
    face_image = np.expand_dims(face_image, axis=0)
    
    return face_image

# --- UTAMA: AKSES KAMERA ---
cap = cv2.VideoCapture(0) # 0 biasanya ID untuk webcam default

if not cap.isOpened():
    print("Kamera tidak terdeteksi!")
    exit()

print("Mulai deteksi... Tekan 'q' untuk keluar.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Gagal membaca frame.")
        break

    # Flip frame agar seperti cermin
    frame = cv2.flip(frame, 1)
    
    # Ambil dimensi frame
    h, w, _ = frame.shape
    
    # Konversi ke RGB untuk MediaPipe
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Deteksi Wajah
    results = face_detection.process(rgb_frame)

    if results.detections:
        for detection in results.detections:
            # Ambil bounding box dari MediaPipe (relative coordinates)
            bboxC = detection.location_data.relative_bounding_box
            
            # Konversi ke koordinat piksel absolut
            x = int(bboxC.xmin * w)
            y = int(bboxC.ymin * h)
            w_box = int(bboxC.width * w)
            h_box = int(bboxC.height * h)

            # Pastikan koordinat tidak keluar batas frame
            x = max(0, x)
            y = max(0, y)
            
            # Crop area wajah
            face_roi = frame[y:y+h_box, x:x+w_box]

            # Jika wajah terdeteksi dengan jelas (ukurannya > 0)
            if face_roi.size > 0:
                try:
                    # Preprocess
                    processed_face = preprocess_input(face_roi)

                    # INFERENSI / PREDIKSI
                    preds = model.predict(processed_face, verbose=0)[0]
                    
                    # Ambil label dengan probabilitas tertinggi
                    label_idx = np.argmax(preds)
                    label = LABELS[label_idx]
                    confidence = preds[label_idx]

                    # --- VISUALISASI ---
                    
                    # Warna kotak berdasarkan emosi (bisa dikustomisasi)
                    color = (0, 255, 0) # Hijau
                    if label in ['angry', 'fearful', 'sad', 'disgusted']:
                        color = (0, 0, 255) # Merah untuk emosi negatif
                    
                    # Gambar kotak di wajah
                    cv2.rectangle(frame, (x, y), (x + w_box, y + h_box), color, 2)
                    
                    # Tulis label dan confidence
                    text = f"{label} ({confidence*100:.1f}%)"
                    cv2.putText(frame, text, (x, y - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                                
                except Exception as e:
                    print(f"Error processing face: {e}")

    # Tampilkan hasil
    cv2.imshow('Real-time Emotion Detection', frame)

    # Tekan 'q' untuk keluar
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Bersihkan
cap.release()
cv2.destroyAllWindows()