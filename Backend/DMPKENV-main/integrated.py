from flask import Flask, jsonify, request
import mysql.connector
import pandas as pd
from flask_cors import CORS
import pickle
from datetime import datetime, timedelta, timezone
import logging
import math # Untuk math.isnan
import os
import numpy as np

# --- Flask Application Initialization ---
app = Flask(__name__)

# --- Configure Logging ---
# logging.basicConfig(level=logging.INFO) # Sudah di-cover oleh app.logger jika dikonfigurasi
app.logger.setLevel(logging.INFO) # Set Flask's logger level

# --- Global CORS Configuration ---
origins_env = os.getenv("FRONTEND_ORIGINS", "*")
origins = "*" if origins_env.strip() == "*" else [origin.strip() for origin in origins_env.split(",") if origin.strip()]
CORS(app, supports_credentials=True, origins=origins)

# --- Database Configuration & Pooling ---
DB_CONFIG = {
    'user': os.getenv('DB_USER', 'trendbox-app'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_DATABASE', os.getenv('DB_NAME', 'trendbox')),
    'connect_timeout': 3,
}

instance_connection_name = os.getenv('INSTANCE_CONNECTION_NAME', '').strip()
if instance_connection_name:
    DB_CONFIG['unix_socket'] = f"/cloudsql/{instance_connection_name}"
else:
    DB_CONFIG['host'] = os.getenv('DB_HOST', '127.0.0.1')
    DB_CONFIG['port'] = int(os.getenv('DB_PORT', '3306'))

from mysql.connector import pooling
db_pool = None
try:
    db_pool = pooling.MySQLConnectionPool(pool_name="trendbox_pool", pool_size=5, **DB_CONFIG)
    print("✅ MySQL Connection Pool initialized")
except Exception as p_err:
    print(f"⚠️ MySQL Pool init defer: {p_err}")

def get_db_connection():
    global db_pool
    try:
        if db_pool:
            return db_pool.get_connection()
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        app.logger.error(f"Error connecting to database: {err}.")
        raise

# --- Emotion Forecasting Model Configuration ---
MODELS = {}
AVAILABLE_EMOTIONS = ['angry', 'fear', 'happy', 'sad', 'surprised']
AVAILABLE_HEAD_LABELS = {'hat', 'hair', 'hijab'}
AVAILABLE_CLOTHING_LABELS = {
    'sweater', 'shorts', 'skirt', 'long_pants', 't-shirt', 'shirt', 'blouse', 'outer'
}
ANALYTICS_SOURCES = {
    'emotion': ('emotion_track', 'emotion'),
    'head': ('head_track', 'label'),
    'clothing': ('clothing_track', 'label'),
}
# Pastikan path 'models/' ini benar relatif terhadap direktori tempat app.py dijalankan
MODEL_PATH_TEMPLATE = 'models/model_prophet_{emotion}.pkl'

# --- In-memory API Logs for Forecasting API ---
FORECAST_API_LOGS = []

def add_forecast_log(level, message):
    """Adds a log entry to the FORECAST_API_LOGS list and logs via app.logger."""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = {"timestamp": timestamp, "level": level, "message": message}
    FORECAST_API_LOGS.append(log_entry)
    if len(FORECAST_API_LOGS) > 200: # Batasi jumlah log dalam memori
        FORECAST_API_LOGS.pop(0)
    
    # Gunakan app.logger Flask untuk output ke konsol/file
    if level.upper() == "ERROR":
        app.logger.error(f"[Forecast API Log] {message}")
    elif level.upper() == "WARNING":
        app.logger.warning(f"[Forecast API Log] {message}")
    else: # INFO atau level lainnya
        app.logger.info(f"[Forecast API Log] {message}")


add_forecast_log("INFO", "Combined Flask API starting up.")

@app.get('/')
def root():
    return jsonify({'status': 'ok', 'service': 'dashboard-api', 'health': '/health'})

@app.get('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'dashboard-api'})


def _bounded_confidence(value):
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


@app.route('/api/realtime/detections', methods=['POST', 'OPTIONS'])
def save_realtime_detections():
    """Persist metadata produced by the browser WebGPU tracking pipeline."""
    if request.method == 'OPTIONS':
        return '', 200

    if request.content_length and request.content_length > 64 * 1024:
        return jsonify({'error': 'Payload is too large'}), 413

    payload = request.get_json(silent=True) or {}
    records = payload.get('records')
    if not isinstance(records, list) or not records:
        return jsonify({'error': 'records must be a non-empty array'}), 400
    if len(records) > 50:
        return jsonify({'error': 'A maximum of 50 records is allowed per request'}), 400

    raw_session_id = str(payload.get('session_id') or 'browser')
    session_id = ''.join(
        character for character in raw_session_id
        if character.isalnum() or character in ('-', '_')
    )[:64] or 'browser'
    timestamp = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
    inserted = {'emotion': 0, 'head': 0, 'clothing': 0}
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for record in records:
            if not isinstance(record, dict):
                continue
            track_id = str(record.get('track_id') or 'unknown')[:32]
            source = f'webgpu:{session_id}:{track_id}'[:128]

            emotion = record.get('emotion')
            if emotion in AVAILABLE_EMOTIONS:
                cursor.execute(
                    """
                    INSERT INTO emotion_track (user_id, emotion, confidence, timestamp)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (source, emotion, _bounded_confidence(record.get('emotion_confidence')), timestamp),
                )
                inserted['emotion'] += 1

            head = record.get('head')
            if head in AVAILABLE_HEAD_LABELS:
                cursor.execute(
                    """
                    INSERT INTO head_track (label, confidence, timestamp, source)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (head, _bounded_confidence(record.get('head_confidence')), timestamp, source),
                )
                inserted['head'] += 1

            clothing = record.get('clothing')
            if clothing in AVAILABLE_CLOTHING_LABELS:
                cursor.execute(
                    """
                    INSERT INTO clothing_track (label, confidence, timestamp, source)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (clothing, _bounded_confidence(record.get('clothing_confidence')), timestamp, source),
                )
                inserted['clothing'] += 1

        conn.commit()
        app.logger.info('Saved WebGPU realtime records: %s', inserted)
        return jsonify({'status': 'ok', 'inserted': inserted}), 201
    except mysql.connector.Error as error:
        if conn:
            conn.rollback()
        app.logger.exception('Failed to save WebGPU realtime records: %s', error)
        return jsonify({'error': 'Database operation failed'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

# --- Load Forecasting Models ---
for emotion in AVAILABLE_EMOTIONS:
    try:
        with open(MODEL_PATH_TEMPLATE.format(emotion=emotion), 'rb') as f:
            MODELS[emotion] = pickle.load(f)
        add_forecast_log("INFO", f"Model for emotion '{emotion}' successfully loaded from {MODEL_PATH_TEMPLATE.format(emotion=emotion)}.")
    except FileNotFoundError:
        add_forecast_log("WARNING", f"Model file for emotion '{emotion}' not found at {MODEL_PATH_TEMPLATE.format(emotion=emotion)}. Please check the path.")
    except Exception as e:
        add_forecast_log("ERROR", f"Failed to load model for emotion '{emotion}'. Error: {e}")

# --- Database Connection Helper ---
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        app.logger.info("Database connection successful.")
        return conn
    except mysql.connector.Error as err:
        app.logger.error(f"Error connecting to database: {err}. Check DB_CONFIG, network, and credentials.")
        raise # Re-raise the error agar bisa ditangani oleh endpoint

def get_analytics_source(metric):
    return ANALYTICS_SOURCES.get(str(metric or 'emotion').lower(), ANALYTICS_SOURCES['emotion'])

# --- Forecasting Helper Functions (from original forecasting app) ---
def get_forecast_accuracy(model, forecast_df_full):
    model_name_for_log = getattr(model, 'model_name', 'unknown_emotion') # Untuk logging
    if not hasattr(model, 'history') or model.history.empty:
        add_forecast_log("WARNING", f"Model '{model_name_for_log}' has no history for accuracy calculation.")
        return 0.0 # Kembalikan float agar konsisten

    # Pastikan kolom 'ds' dan 'y' ada di model.history
    if 'ds' not in model.history.columns or 'y' not in model.history.columns:
        add_forecast_log("WARNING", f"Model history for '{model_name_for_log}' is missing 'ds' or 'y' columns for accuracy.")
        return 0.0

    merged_df = pd.merge(forecast_df_full[['ds', 'yhat']], model.history[['ds', 'y']], on='ds', how='inner')
    
    if merged_df.empty:
        add_forecast_log("INFO", f"For model '{model_name_for_log}', no overlapping data between forecast and history for accuracy.")
        return 0.0
        
    # Hapus baris jika actual (y) atau prediksi history (yhat) adalah NaN
    merged_df.dropna(subset=['y', 'yhat'], inplace=True) 
    if merged_df.empty:
        add_forecast_log("INFO", f"For model '{model_name_for_log}', data for accuracy became empty after dropping NaNs.")
        return 0.0

    y_actual = merged_df['y'].astype(float) # Pastikan tipe data float
    y_hat_hist = merged_df['yhat'].astype(float) # Pastikan tipe data float

    if len(y_actual) == 0:
        return 0.0
    
    # Perhitungan MAPE yang lebih aman
    errors = abs(y_hat_hist - y_actual)
    non_zero_actuals_mask = (y_actual != 0)
    
    if non_zero_actuals_mask.sum() == 0: # Jika semua actuals adalah nol
        # Jika semua prediksi juga nol, akurasi 100%, jika tidak 0%
        return 100.0 if (y_hat_hist == 0).all() else 0.0

    # Hitung persentase error hanya untuk actuals yang tidak nol
    percentage_errors = errors[non_zero_actuals_mask] / y_actual[non_zero_actuals_mask]
    mape = percentage_errors.mean() * 100
    
    if pd.isna(mape): # Jika mape adalah NaN (misal, tidak ada non_zero_actuals)
        accuracy = 0.0
    else:
        accuracy = 100.0 - mape
    
    # Pastikan akurasi antara 0 dan 100
    accuracy = max(0.0, min(100.0, accuracy))
    return round(accuracy, 2)


def get_weekly_trend(forecast_df_full):
    if 'yhat' not in forecast_df_full.columns or len(forecast_df_full) < 14 :
        return 'N/A' # Tidak cukup data
    
    # Pastikan 'yhat' adalah numerik, ganti non-numerik dengan NaN
    forecast_df_full['yhat'] = pd.to_numeric(forecast_df_full['yhat'], errors='coerce')
    # Hapus baris dengan yhat NaN setelah konversi
    forecast_df_full.dropna(subset=['yhat'], inplace=True)

    if len(forecast_df_full) < 14: # Cek ulang setelah dropna
        return 'N/A'

    last_week_yhat = forecast_df_full.tail(7)['yhat']
    prev_week_yhat = forecast_df_full.tail(14).head(7)['yhat']

    if last_week_yhat.empty or prev_week_yhat.empty: # Jika salah satu kosong setelah filter
        return 'N/A'

    last_week_mean = last_week_yhat.mean()
    prev_week_mean = prev_week_yhat.mean()

    if pd.isna(last_week_mean) or pd.isna(prev_week_mean): # Jika mean adalah NaN
        return 'N/A'

    if prev_week_mean == 0:
        if last_week_mean == 0:
            return '+0.00%'
        # Jika prev_week_mean adalah 0 dan last_week_mean tidak, ini adalah perubahan tak terhingga.
        # Anda mungkin ingin mengembalikan 'Infinite Increase/Decrease' atau 'N/A'.
        # Untuk kesederhanaan, kita bisa anggap ini perubahan besar.
        return '+100.00%' if last_week_mean > 0 else '-100.00%' # Contoh representasi
    else:
        # Gunakan abs(prev_week_mean) di pembagi untuk persentase perubahan yang lebih stabil
        delta = ((last_week_mean - prev_week_mean) / abs(prev_week_mean)) * 100 
        return f"{'+' if delta >= 0 else ''}{round(delta, 2)}%"


# --- Combined API Endpoints ---

@app.route('/api/summary', methods=['GET', 'OPTIONS'])
def db_summary():
    if request.method == 'OPTIONS':
        app.logger.info("--- /api/summary (DB) OPTIONS request hit ---")
        return '', 200 
    
    conn = None
    try:
        app.logger.info("--- /api/summary (DB) GET request hit ---")
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS count FROM emotion_track WHERE timestamp >= CURDATE()")
        detected_faces_row = cursor.fetchone()
        detected_faces = detected_faces_row['count'] if detected_faces_row else 0

        cursor.execute("""
            SELECT emotion
            FROM emotion_track
            WHERE timestamp >= CURDATE()
            GROUP BY emotion
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        dominant_emotion = row['emotion'] if row else 'N/A'

        def get_attribute_summary(table_name):
            # table_name is only supplied from the fixed allowlist below.
            cursor.execute(f"""
                SELECT label, COUNT(*) AS count
                FROM {table_name}
                WHERE timestamp >= CURDATE()
                GROUP BY label
                ORDER BY count DESC, label ASC
            """)
            distribution = cursor.fetchall()
            total = sum(int(item['count']) for item in distribution)
            return {
                'total': total,
                'dominant': distribution[0]['label'] if distribution else 'N/A',
                'distribution': distribution,
            }

        attribute_summary = {
            'head': get_attribute_summary('head_track'),
            'clothing': get_attribute_summary('clothing_track'),
        }

        cursor.execute("""
            SELECT COUNT(*) AS total FROM emotion_track
            WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1)
        """)
        total_this_week_row = cursor.fetchone()
        total_this_week = total_this_week_row['total'] if total_this_week_row and total_this_week_row['total'] else 1

        cursor.execute("""
            SELECT COUNT(*) AS total FROM emotion_track
            WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE() - INTERVAL 7 DAY, 1)
        """)
        total_last_week_row = cursor.fetchone()
        total_last_week = total_last_week_row['total'] if total_last_week_row and total_last_week_row['total'] else 1

        cursor.execute("""
            SELECT emotion, COUNT(*) AS count FROM emotion_track
            WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1)
            GROUP BY emotion
        """)
        this_week_counts_raw = cursor.fetchall()
        this_week = {r['emotion']: (r['count'] / total_this_week) * 100 for r in this_week_counts_raw}


        cursor.execute("""
            SELECT emotion, COUNT(*) AS count FROM emotion_track
            WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE() - INTERVAL 7 DAY, 1)
            GROUP BY emotion
        """)
        last_week_counts_raw = cursor.fetchall()
        last_week = {r['emotion']: (r['count'] / total_last_week) * 100 for r in last_week_counts_raw}


        changes = {}
        all_emotions_db = set(this_week.keys()).union(last_week.keys())
        if all_emotions_db : # Cek jika ada emosi
            for emotion_db in all_emotions_db:
                current = this_week.get(emotion_db, 0.0)
                last = last_week.get(emotion_db, 0.0)
                if last == 0:
                    changes[emotion_db] = 100.0 if current > 0 else 0.0 # Perubahan dari 0 ke X adalah 100%
                else:
                    changes[emotion_db] = round(((current - last) / last) * 100, 2)
        
        return jsonify({
            'detected_faces': detected_faces,
            'dominant_emotion': dominant_emotion,
            'weekly_changes': changes,
            'attribute_summary': attribute_summary,
        })
    except Exception as db_err:
        app.logger.error(f"Database unavailable for /api/summary: {db_err}")
        return jsonify({
            'detected_faces': 0,
            'dominant_emotion': 'N/A',
            'weekly_changes': {},
            'attribute_summary': {
                'head': {'total': 0, 'dominant': 'N/A', 'distribution': []},
                'clothing': {'total': 0, 'dominant': 'N/A', 'distribution': []}
            }
        })
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/api/logs', methods=['GET', 'OPTIONS'])
def db_logs():
    if request.method == 'OPTIONS':
        return '', 200

    conn = None
    try:
        conn = get_db_connection()
        query = """
            SELECT timestamp, user_id AS person, emotion, confidence
            FROM emotion_track
            ORDER BY timestamp DESC LIMIT 50
        """
        df = pd.read_sql(query, conn)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%dT%H:%M:%S')
            df.fillna(value=pd.NA, inplace=True)
            records = df.to_dict(orient='records')
            cleaned_records = [{k: (None if pd.isna(v) else v) for k, v in record.items()} for record in records]
            return jsonify(cleaned_records)
        else:
            return jsonify([]) 
    except Exception as db_err:
        app.logger.error(f"Database unavailable for /api/logs: {db_err}")
        return jsonify([])
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/api/distribution', methods=['GET', 'OPTIONS'])
def db_distribution():
    if request.method == 'OPTIONS':
        return '', 200

    conn = None
    try:
        range_param = request.args.get('range', 'today')
        metric = request.args.get('metric', 'emotion').lower()
        table_name, category_column = get_analytics_source(metric)
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        condition = ""
        condition = ""
        if range_param == 'today':
            condition = "timestamp >= CURDATE()"
        elif range_param == 'week':
            condition = "timestamp >= CURDATE() - INTERVAL 7 DAY"
        elif range_param == 'month':
            condition = "timestamp >= CURDATE() - INTERVAL 30 DAY"
        else:
            condition = "timestamp >= CURDATE()"

        query = f"""
            SELECT {category_column} AS category,
                   {category_column} AS emotion,
                   {category_column} AS label,
                   COUNT(*) AS count
            FROM {table_name}
            WHERE {condition}
            GROUP BY {category_column}
        """
        cursor.execute(query)
        data = cursor.fetchall()

        if not data and range_param in ('month', 'week'):
            fallback_query = f"""
                SELECT {category_column} AS category,
                       {category_column} AS emotion,
                       {category_column} AS label,
                       COUNT(*) AS count
                FROM {table_name}
                GROUP BY {category_column}
            """
            cursor.execute(fallback_query)
            data = cursor.fetchall()

        return jsonify(data)
    except Exception as db_err:
        app.logger.error(f"Database unavailable for /api/distribution: {db_err}")
        return jsonify([])
    finally:
        if conn and conn.is_connected():
            conn.close()
            app.logger.info(f"--- Database connection closed for /api/distribution (DB) range: {range_param} ---")


@app.route('/api/trends/today', methods=['GET', 'OPTIONS'])
def db_trends_today():
    if request.method == 'OPTIONS':
        return '', 200

    conn = None
    try:
        conn = get_db_connection()
        metric = request.args.get('metric', 'emotion').lower()
        table_name, category_column = get_analytics_source(metric)
        df = pd.read_sql(f"""
            SELECT {category_column} AS category, HOUR(timestamp) as hour, COUNT(*) as count
            FROM {table_name}
            WHERE timestamp >= CURDATE()
            GROUP BY {category_column}, hour
            ORDER BY hour
        """, conn)
        result = {}
        if not df.empty:
            for category, group in df.groupby('category'):
                result[category] = {'hours': group['hour'].tolist(), 'counts': group['count'].tolist()}
        return jsonify(result)
    except Exception as db_err:
        app.logger.error(f"Database unavailable for /api/trends/today: {db_err}")
        return jsonify({})
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/api/trends/weekly', methods=['GET', 'OPTIONS'])
def db_trends_weekly():
    if request.method == 'OPTIONS':
        return '', 200

    conn = None
    try:
        conn = get_db_connection()
        metric = request.args.get('metric', 'emotion').lower()
        table_name, category_column = get_analytics_source(metric)
        query = f"""
            SELECT
                {category_column} AS category,
                WEEKDAY(timestamp) as day_of_week,
                COUNT(*) as count
            FROM {table_name}
            WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1)
            GROUP BY {category_column}, day_of_week
            ORDER BY day_of_week
        """
        df = pd.read_sql(query, conn)
        result = {}
        if not df.empty:
            for category, group in df.groupby('category'):
                result[category] = {'days': group['day_of_week'].tolist(), 'counts': group['count'].tolist()}
        return jsonify(result)
    except Exception as db_err:
        app.logger.error(f"Database unavailable for /api/trends/weekly: {db_err}")
        return jsonify({})
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/api/trends', methods=['GET', 'OPTIONS'])
def db_trends_all():
    if request.method == 'OPTIONS':
        return '', 200

    conn = None
    try:
        conn = get_db_connection()
        metric = request.args.get('metric', 'emotion').lower()
        table_name, category_column = get_analytics_source(metric)
        df = pd.read_sql(f"""
            SELECT {category_column} AS category, DATE(timestamp) as date, COUNT(*) as count
            FROM {table_name}
            GROUP BY {category_column}, DATE(timestamp)
            ORDER BY date
        """, conn)
        result = {}
        if not df.empty:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            for category, group in df.groupby('category'):
                result[category] = {'dates': group['date'].tolist(), 'counts': group['count'].tolist()}
        return jsonify(result)
    except Exception as db_err:
        app.logger.error(f"Database unavailable for /api/trends: {db_err}")
        return jsonify({})
    finally:
        if conn and conn.is_connected():
            conn.close()


# Endpoint from original Emotion Forecasting API
def get_dynamic_label_history(data_type, label):
    table_name, category_column = get_analytics_source(data_type)
    allowed_labels = {
        'emotion': set(AVAILABLE_EMOTIONS),
        'head': set(AVAILABLE_HEAD_LABELS),
        'clothing': set(AVAILABLE_CLOTHING_LABELS),
    }
    if data_type not in allowed_labels or label not in allowed_labels[data_type]:
        return pd.DataFrame(columns=['ds', 'y'])

    conn = get_db_connection()
    try:
        query = f"""
            SELECT DATE(timestamp) AS ds, COUNT(*) AS y
            FROM {table_name}
            WHERE {category_column} = %s
            GROUP BY DATE(timestamp)
            ORDER BY ds
        """
        history = pd.read_sql(query, conn, params=[label])
    finally:
        if conn and conn.is_connected():
            conn.close()

    if history.empty:
        return pd.DataFrame(columns=['ds', 'y'])
    history['ds'] = pd.to_datetime(history['ds'])
    history['y'] = pd.to_numeric(history['y'], errors='coerce').fillna(0).astype(float)
    full_dates = pd.date_range(history['ds'].min(), history['ds'].max(), freq='D')
    history = history.set_index('ds').reindex(full_dates, fill_value=0).rename_axis('ds').reset_index()
    return history

def build_dynamic_forecast(data_type, label, forecast_days, start_date=None, end_date=None):
    history = get_dynamic_label_history(data_type, label)
    if history.empty:
        return {'forecast_points': [], 'accuracy': 0.0, 'trend': 'N/A'}

    y = history['y'].to_numpy(dtype=float)
    x = np.arange(len(y), dtype=float)
    if len(y) >= 2:
        slope, intercept = np.polyfit(x, y, 1)
    else:
        slope, intercept = 0.0, float(y[0])

    fitted = np.maximum(0, intercept + slope * x)
    residual_std = float(np.std(y - fitted)) if len(y) > 1 else 0.0
    denominator = max(float(np.mean(y)), 1.0)
    accuracy = max(0.0, min(100.0, 100.0 * (1.0 - float(np.mean(np.abs(y - fitted))) / denominator)))

    periods = max(1, min(int(forecast_days), 90))
    if end_date:
        requested_end = pd.to_datetime(end_date).tz_localize(None).normalize()
        history_end = pd.to_datetime(history['ds'].max()).tz_localize(None).normalize()
        days_to_requested_end = max(0, (requested_end - history_end).days)
        periods = max(periods, min(days_to_requested_end, 1095))
    future_dates = pd.date_range(history['ds'].max() + pd.Timedelta(days=1), periods=periods, freq='D')
    all_dates = pd.DatetimeIndex(history['ds'].tolist() + future_dates.tolist())
    recent_window = y[-min(7, len(y)):]
    weights = np.arange(1, len(recent_window) + 1, dtype=float)
    forecast_base = float(np.average(recent_window, weights=weights))
    median_change = float(np.median(np.diff(recent_window))) if len(recent_window) > 1 else 0.0
    max_daily_change = max(0.25, forecast_base * 0.2)
    damped_change = float(np.clip(median_change, -max_daily_change, max_daily_change)) * 0.25
    future_predictions = np.maximum(
        0,
        forecast_base + damped_change * np.arange(1, periods + 1, dtype=float),
    )
    predictions = np.concatenate([fitted, future_predictions])
    actual_by_date = {pd.Timestamp(row.ds): float(row.y) for row in history.itertuples()}

    start_filter = pd.to_datetime(start_date) if start_date else all_dates.min()
    end_filter = pd.to_datetime(end_date) if end_date else all_dates.max()
    points = []
    for date_value, prediction in zip(all_dates, predictions):
        if date_value < start_filter or date_value > end_filter:
            continue
        points.append({
            'name': date_value.strftime('%Y-%m-%d'),
            'actual': actual_by_date.get(pd.Timestamp(date_value)),
            'yhat': round(float(prediction), 2),
            'yhat_lower': round(max(0.0, float(prediction) - 1.96 * residual_std), 2),
            'yhat_upper': round(float(prediction) + 1.96 * residual_std, 2),
        })

    recent = float(np.mean(y[-7:])) if len(y) else 0.0
    previous = float(np.mean(y[-14:-7])) if len(y) >= 14 else 0.0
    if len(y) < 14:
        trend = 'N/A'
    elif previous == 0:
        trend = '+100.0%' if recent > 0 else '+0.0%'
    else:
        change = ((recent - previous) / abs(previous)) * 100
        trend = f"{'+' if change >= 0 else ''}{round(change, 2)}%"
    return {'forecast_points': points, 'accuracy': round(accuracy, 2), 'trend': trend}

@app.route('/api/forecast/options', methods=['GET'])
def forecast_options():
    return jsonify({
        'emotion': sorted(AVAILABLE_EMOTIONS),
        'head': sorted(AVAILABLE_HEAD_LABELS),
        'clothing': sorted(AVAILABLE_CLOTHING_LABELS),
    })

@app.route('/api/forecast', methods=['POST', 'OPTIONS'])
def get_forecast_data():
    app.logger.info(f"--- {request.method} /api/forecast ---")
    if request.method == 'OPTIONS':
        app.logger.info("Responding to OPTIONS request for /api/forecast")
        return '', 200 

    add_forecast_log("INFO", f"Received POST request to '/api/forecast' with payload: {request.json}")
    
    try:
        payload = request.get_json()
        if not payload: 
            add_forecast_log("WARNING", "Request to '/api/forecast' without JSON payload.")
            return jsonify({"error": "Invalid request payload"}), 400
            
        data_type = str(payload.get('data_type', 'emotion')).lower()
        selected_emotion = payload.get('label') or payload.get('emotion', 'happy')
        if data_type in ('head', 'clothing'):
            forecast_days_count = int(payload.get('forecast_days', 7))
            dynamic_result = build_dynamic_forecast(
                data_type,
                selected_emotion,
                forecast_days_count,
                payload.get('start_date'),
                payload.get('end_date'),
            )
            return jsonify({
                **dynamic_result,
                'data_type': data_type,
                'label': selected_emotion,
                'forecast_days': forecast_days_count,
                'granularity': 'daily',
            })

        if selected_emotion not in MODELS: 
            add_forecast_log("ERROR", f"Model for emotion '{selected_emotion}' not found during request to '/api/forecast'.")
            return jsonify({"error": f"Model '{selected_emotion}' not found"}), 404
            
        model = MODELS[selected_emotion]
        if not hasattr(model, 'history') or model.history.empty: 
            add_forecast_log("ERROR", f"Model '{selected_emotion}' has no history data during request to '/api/forecast'.")
            # Kembalikan data default jika tidak ada history, agar frontend tidak error
            return jsonify({
                'forecast_points': [], # List kosong untuk chart
                'accuracy': 0.0,
                'trend': 'N/A',
                'emotion': selected_emotion, 
                'message': f"Model '{selected_emotion}' has no history data."
            }), 200 # Gunakan 200 OK karena ini kondisi data, bukan error server

        forecast_days_count = max(1, min(int(payload.get('forecast_days', 7)), 90))
        granularity_frontend = payload.get('granularity', 'daily')
        prophet_freq = {"hourly": "H", "daily": "D", "weekly": "W", "monthly": "M"}.get(granularity_frontend.lower(), 'D')
        start_date_str, end_date_str = payload.get('start_date'), payload.get('end_date')

        generated_periods = forecast_days_count
        if end_date_str:
            history_end = pd.to_datetime(model.history['ds']).max().tz_localize(None)
            requested_end = pd.to_datetime(end_date_str).tz_localize(None)
            seconds_to_requested_end = max(0.0, (requested_end - history_end).total_seconds())
            if prophet_freq == "H":
                periods_to_requested_end = math.ceil(seconds_to_requested_end / 3600)
                maximum_extension = 24 * 365
            elif prophet_freq == "W":
                periods_to_requested_end = math.ceil(seconds_to_requested_end / (7 * 86400))
                maximum_extension = 156
            elif prophet_freq == "M":
                periods_to_requested_end = math.ceil(seconds_to_requested_end / (30 * 86400))
                maximum_extension = 36
            else:
                periods_to_requested_end = math.ceil(seconds_to_requested_end / 86400)
                maximum_extension = 1095
            generated_periods = max(
                forecast_days_count,
                min(periods_to_requested_end, maximum_extension),
            )

        future_df = model.make_future_dataframe(periods=generated_periods, freq=prophet_freq)
        forecast_df_full = model.predict(future_df)
        
        # Gabungkan dengan history. 'ds' di history dan forecast_df_full harusnya sudah datetime
        output_df = pd.merge(forecast_df_full[['ds', 'yhat', 'yhat_lower', 'yhat_upper']], 
                             model.history[['ds', 'y']], 
                             on='ds', 
                             how='left') # 'left' join untuk mempertahankan semua tanggal forecast

        # Filter berdasarkan tanggal jika ada
        if start_date_str and end_date_str:
            try:
                # Konversi ds ke naive datetime untuk perbandingan yang konsisten
                output_df['ds'] = pd.to_datetime(output_df['ds']).dt.tz_localize(None)
                start_dt_filter = pd.to_datetime(start_date_str).tz_localize(None)
                end_dt_filter = pd.to_datetime(end_date_str).tz_localize(None)
                output_df = output_df[(output_df['ds'] >= start_dt_filter) & (output_df['ds'] <= end_dt_filter)]
            except Exception as e: 
                add_forecast_log("ERROR", f"Error parsing or applying date filter in '/api/forecast': {e}")
                # Lanjutkan tanpa filter jika ada error tanggal

        recharts_data_list_clean = []
        if not output_df.empty:
            df_for_recharts = output_df.rename(columns={'y': 'actual', 'ds': 'name'})
            df_for_recharts['name'] = pd.to_datetime(df_for_recharts['name']).dt.strftime('%Y-%m-%d') # Format 'name'
            
            # Konversi DataFrame ke list of dictionaries
            recharts_data_list_raw = df_for_recharts.to_dict(orient='records')

            # **PERBAIKAN UTAMA: Ganti float NaN dan pd.NaT dengan None (JSON null)**
            for record in recharts_data_list_raw:
                cleaned_record = {}
                for key, value in record.items():
                    if (isinstance(value, float) and math.isnan(value)) or pd.isna(value): # pd.isna() menangani NaN, NaT
                        cleaned_record[key] = None 
                    else:
                        cleaned_record[key] = value
                recharts_data_list_clean.append(cleaned_record)
        
        current_accuracy = get_forecast_accuracy(model, forecast_df_full)
        current_trend = get_weekly_trend(forecast_df_full)
        
        add_forecast_log("INFO", f"Successfully processed request to '/api/forecast' for emotion '{selected_emotion}'. Returning {len(recharts_data_list_clean)} data points. Accuracy: {current_accuracy}, Trend: {current_trend}")
        
        # Logging data sampel untuk debugging
        if recharts_data_list_clean:
             app.logger.debug(f"Sample data point for {selected_emotion} (first): {recharts_data_list_clean[0]}")
        else:
             app.logger.debug(f"No data points to return for {selected_emotion} after processing.")


        return jsonify({
            'forecast_points': recharts_data_list_clean,
            'accuracy': current_accuracy,
            'trend': current_trend,
            'emotion': selected_emotion, 
            'label': selected_emotion,
            'data_type': 'emotion',
            'forecast_days': forecast_days_count, 
            'granularity': granularity_frontend
        })
    except Exception as e:
        add_forecast_log("ERROR", f"Major unhandled error in /api/forecast: {e}")
        app.logger.error(f"Exception in /api/forecast: {e}", exc_info=True) # Tampilkan traceback lengkap
        return jsonify({"error": "Internal server error on forecast", "details": str(e)}), 500


@app.route('/api/forecast_summary', methods=['GET', 'OPTIONS'])
def api_forecast_summary():
    app.logger.info(f"--- {request.method} /api/forecast_summary ---")
    if request.method == 'OPTIONS':
        return '', 200 

    add_forecast_log("INFO", "Received GET request to '/api/forecast_summary'.")
    data_type = request.args.get('data_type', 'emotion').lower()
    if data_type in ('head', 'clothing'):
        labels = sorted(AVAILABLE_HEAD_LABELS if data_type == 'head' else AVAILABLE_CLOTHING_LABELS)
        accuracies, trends = {}, {}
        for label in labels:
            result = build_dynamic_forecast(data_type, label, 7)
            accuracies[label] = result['accuracy']
            trends[label] = result['trend']
        return jsonify({'data_type': data_type, 'accuracies': accuracies, 'trends': trends})

    summary_forecast_days, summary_freq = 7, 'D' # default 7 hari, frekuensi harian
    accuracies, trends = {}, {}
    
    for emotion_key in AVAILABLE_EMOTIONS:
        try:
            if emotion_key not in MODELS or not hasattr(MODELS[emotion_key], 'history') or MODELS[emotion_key].history.empty:
                add_forecast_log("WARNING", f"Model/history for forecast summary (emotion: '{emotion_key}') is missing.")
                accuracies[emotion_key], trends[emotion_key] = 0.0, "N/A" # Default jika model/history tidak ada
                continue # Lanjut ke emosi berikutnya
            
            model = MODELS[emotion_key]
            future = model.make_future_dataframe(periods=summary_forecast_days, freq=summary_freq)
            forecast = model.predict(future)
            accuracies[emotion_key] = get_forecast_accuracy(model, forecast)
            trends[emotion_key] = get_weekly_trend(forecast)
        except Exception as e:
            add_forecast_log("ERROR", f"Error processing summary for emotion '{emotion_key}': {e}")
            app.logger.error(f"Exception in /api/forecast_summary for emotion {emotion_key}: {e}", exc_info=True)
            accuracies[emotion_key], trends[emotion_key] = 0.0, "Error" # Tandai error per emosi


    add_forecast_log("INFO", "Successfully processed request to '/api/forecast_summary'.")
    return jsonify({"accuracies": accuracies, "trends": trends})


@app.route('/api/forecast_distribution', methods=['GET', 'OPTIONS'])
def api_forecast_distribution():
    app.logger.info(f"--- {request.method} /api/forecast_distribution with args: {request.args} ---")
    if request.method == 'OPTIONS':
        return '', 200

    add_forecast_log("INFO", f"Received GET request to '/api/forecast_distribution' with args: {request.args}")
    time_range_param = request.args.get('range', 'today')
    
    # Tentukan start_date dan end_date berdasarkan time_range_param
    end_date_utc = datetime.now(timezone.utc) # Akhir rentang adalah sekarang (UTC)
    if time_range_param == 'today': 
        start_date_utc = end_date_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_range_param == 'week': 
        start_date_utc = (end_date_utc - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_range_param == 'month': 
        # Asumsi 'month' adalah 30 hari terakhir dari hari ini
        start_date_utc = (end_date_utc - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
    else: 
        add_forecast_log("WARNING", f"Invalid 'range' parameter in '/api/forecast_distribution': {time_range_param}. Defaulting to 'today'.")
        return jsonify({"error": "Invalid 'range' parameter. Use 'today', 'week', or 'month'."}), 400

    distribution_result = []
    for emotion_name in AVAILABLE_EMOTIONS:
        try:
            if emotion_name not in MODELS or not hasattr(MODELS[emotion_name], 'history') or MODELS[emotion_name].history.empty:
                add_forecast_log("WARNING", f"Model/history for forecast distribution (emotion: '{emotion_name}') is missing.")
                distribution_result.append({"emotion": emotion_name, "count": 0}); 
                continue
            
            history_df = MODELS[emotion_name].history.copy()
            history_df['ds'] = pd.to_datetime(history_df['ds']) # Pastikan 'ds' adalah datetime

            # Pastikan 'ds' di history_df adalah timezone-aware (UTC) untuk perbandingan yang benar
            if history_df['ds'].dt.tz is None:
                history_df['ds'] = history_df['ds'].dt.tz_localize('UTC', ambiguous='infer') # Atau zona waktu data Anda jika diketahui
            else:
                history_df['ds'] = history_df['ds'].dt.tz_convert('UTC') # Konversi ke UTC jika sudah aware

            # Filter history_df berdasarkan rentang tanggal UTC
            filtered_history = history_df[(history_df['ds'] >= start_date_utc) & (history_df['ds'] <= end_date_utc)]
            
            emotion_count = 0
            if not filtered_history.empty and 'y' in filtered_history.columns:
                # Pastikan 'y' adalah numerik dan ganti NaN dengan 0 sebelum sum
                emotion_count = pd.to_numeric(filtered_history['y'], errors='coerce').fillna(0).sum()
            
            distribution_result.append({"emotion": emotion_name, "count": int(emotion_count)})
        except Exception as e:
            add_forecast_log("ERROR", f"Error processing distribution for emotion '{emotion_name}': {e}")
            app.logger.error(f"Exception in /api/forecast_distribution for {emotion_name}: {e}", exc_info=True)
            distribution_result.append({"emotion": emotion_name, "count": 0, "error": str(e)})

    add_forecast_log("INFO", f"Successfully processed request to '/api/forecast_distribution' for range '{time_range_param}'.")
    return jsonify(distribution_result)


@app.route('/api/forecast_trends_today', methods=['GET', 'OPTIONS'])
def api_forecast_trends_today():
    app.logger.info(f"--- {request.method} /api/forecast_trends_today ---")
    if request.method == 'OPTIONS':
        return '', 200

    add_forecast_log("INFO", "Received GET request to '/api/forecast_trends_today'.")
    daily_trends = {}
    
    # Tentukan 'today' dan 'yesterday' dalam UTC untuk konsistensi dengan data model (jika model dilatih dengan UTC)
    # Jika model Anda menggunakan waktu lokal, sesuaikan ini.
    today_dt_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_dt_utc = today_dt_utc - timedelta(days=1)

    for emotion_key in AVAILABLE_EMOTIONS:
        try:
            if emotion_key not in MODELS:
                daily_trends[emotion_key] = "N/A (Model missing)"
                continue
            
            model = MODELS[emotion_key]
            if not hasattr(model, 'history') or model.history.empty:
                daily_trends[emotion_key] = "N/A (No history)"
                continue

            # Dapatkan tanggal terakhir dari history untuk menentukan berapa banyak periode forecast yang dibutuhkan
            last_history_date_naive = pd.to_datetime(model.history['ds'].max())
            if pd.isna(last_history_date_naive):
                 daily_trends[emotion_key] = "N/A (History date invalid)"
                 continue

            # Asumsikan history 'ds' adalah naive atau bisa dikonversi ke UTC
            last_history_date_utc = last_history_date_naive.tz_localize('UTC', ambiguous='infer') if last_history_date_naive.tzinfo is None else last_history_date_naive.tz_convert('UTC')

            # Hitung periode yang dibutuhkan untuk forecast hingga hari ini
            periods_needed = 0
            if today_dt_utc > last_history_date_utc:
                periods_needed = (today_dt_utc - last_history_date_utc).days
            
            # Forecast setidaknya untuk 1 hari ke depan, atau lebih jika history tertinggal
            future_df = model.make_future_dataframe(periods=max(1, periods_needed + 1), freq='D') 
            forecast = model.predict(future_df)

            # Pastikan 'ds' di forecast adalah UTC untuk perbandingan
            forecast['ds'] = pd.to_datetime(forecast['ds'])
            if forecast['ds'].dt.tz is None:
                forecast['ds'] = forecast['ds'].dt.tz_localize('UTC', ambiguous='infer')
            else:
                forecast['ds'] = forecast['ds'].dt.tz_convert('UTC')

            # Dapatkan prediksi untuk hari ini dan kemarin
            today_forecast_series = forecast[forecast['ds'] == today_dt_utc]['yhat']
            yesterday_forecast_series = forecast[forecast['ds'] == yesterday_dt_utc]['yhat']

            if today_forecast_series.empty or yesterday_forecast_series.empty:
                add_forecast_log("WARNING", f"No forecast data for today or yesterday for emotion '{emotion_key}'.")
                daily_trends[emotion_key] = "N/A (Data missing for trend)"
                continue

            today_yhat = today_forecast_series.iloc[0]
            yesterday_yhat = yesterday_forecast_series.iloc[0]

            if pd.isna(today_yhat) or pd.isna(yesterday_yhat):
                daily_trends[emotion_key] = "N/A (Prediction NaN for trend)"
                continue
            
            if yesterday_yhat == 0:
                trend_val = '+0.00%' if today_yhat >= 0 else '-0.00%' # Atau representasi lain untuk perubahan dari nol
            else:
                delta = ((today_yhat - yesterday_yhat) / abs(yesterday_yhat)) * 100 # Gunakan abs untuk penyebut
                trend_val = f"{'+' if delta >= 0 else ''}{round(delta, 2)}%"
            
            daily_trends[emotion_key] = trend_val
        except Exception as e:
            add_forecast_log("ERROR", f"Error processing daily trend for emotion '{emotion_key}': {e}")
            app.logger.error(f"Exception in /api/forecast_trends_today for {emotion_key}: {e}", exc_info=True)
            daily_trends[emotion_key] = "Error"


    add_forecast_log("INFO", "Successfully processed request to '/api/forecast_trends_today'.")
    return jsonify(daily_trends)


@app.route('/api/forecast_logs', methods=['GET', 'OPTIONS'])
def get_forecast_api_logs():
    app.logger.info(f"--- {request.method} /api/forecast_logs ---")
    if request.method == 'OPTIONS':
        return '', 200
    add_forecast_log("INFO", "Received GET request to '/api/forecast_logs'.")
    return jsonify(list(FORECAST_API_LOGS)) # Kirim salinan list


if __name__ == '__main__':
    # Start Flask server immediately on 0.0.0.0:5000 without blocking startup
    app.run(debug=False, port=5000, host='0.0.0.0', threaded=True)

