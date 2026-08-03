import tensorflow as tf

# Muat model Keras .h5 Anda
model = tf.keras.models.load_model('model_emotion2.h5')

# Buat converter TFLite
converter = tf.lite.TFLiteConverter.from_keras_model(model)

# (Opsional tapi disarankan) Terapkan optimisasi, misalnya kuantisasi float16
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_types = [tf.float16]

# Lakukan konversi
tflite_model = converter.convert()

# Simpan model .tflite
with open('model_emotion2.tflite', 'wb') as f:
    f.write(tflite_model)

print("Model berhasil dikonversi ke model_emotion2.tflite")