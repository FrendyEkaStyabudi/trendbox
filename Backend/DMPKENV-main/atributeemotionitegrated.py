from flask import Flask, jsonify, request
import mysql.connector
import pandas as pd
from flask_cors import CORS
import pickle
from datetime import datetime, timedelta, timezone
import logging
import math
import os

# --- Flask Application Initialization ---
app = Flask(__name__)

# --- Configure Logging ---
app.logger.setLevel(logging.INFO)

# --- Global CORS Configuration ---
origins = ["http://localhost:3000"]
CORS(app, supports_credentials=True, origins=origins)

# --- Database Configuration ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'yamanote.proxy.rlwy.net'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu'),
    'database': os.getenv('DB_DATABASE', 'railway'),
    'port': os.getenv('DB_PORT', 59862),
}

# ==========================================
# --- 1. INTEGRATION CONFIGURATION ---
# ==========================================

ALLOWED_ITEMS = {
    'clothing': ['t-shirt', 'sweater', 'outer', 'long_pants', 'shorts', 'shirt', 'blouse', 'skirt'],
    'head': ['hair', 'hat', 'hijab'],
    'emotion': ['angry', 'fear', 'happy', 'sad', 'surprised']
}

CATEGORY_CONFIG = {
    'emotion': {'table_name': 'emotion_track', 'column_name': 'emotion'},
    'clothing': {'table_name': 'clothing_track', 'column_name': 'label'},
    'head': {'table_name': 'head_track', 'column_name': 'label'}
}

# --- Model Configuration ---
MODELS = {}
MODEL_PATH_TEMPLATE = 'models/model_prophet_{name}.pkl'
FORECAST_API_LOGS = []

def add_forecast_log(level, message):
    timestamp = datetime.now(timezone.utc).isoformat()
    FORECAST_API_LOGS.append({"timestamp": timestamp, "level": level, "message": message})
    if len(FORECAST_API_LOGS) > 200: FORECAST_API_LOGS.pop(0)
    if level.upper() == "ERROR": app.logger.error(f"[Forecast API Log] {message}")
    elif level.upper() == "WARNING": app.logger.warning(f"[Forecast API Log] {message}")
    else: app.logger.info(f"[Forecast API Log] {message}")

add_forecast_log("INFO", "Combined Flask API starting up.")

# --- Load Models ---
loaded_models_count = 0
for category, items in ALLOWED_ITEMS.items():
    for item_name in items:
        if item_name in MODELS: continue 
        try:
            path = MODEL_PATH_TEMPLATE.format(name=item_name)
            with open(path, 'rb') as f:
                MODELS[item_name] = pickle.load(f)
            loaded_models_count += 1
        except Exception:
            pass 

add_forecast_log("INFO", f"Total {loaded_models_count} Prophet models loaded.")

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        app.logger.error(f"Error connecting to database: {err}")
        raise

def get_forecast_accuracy(model, forecast_df_full):
    if not hasattr(model, 'history') or model.history.empty: return 0.0
    if 'ds' not in model.history.columns or 'y' not in model.history.columns: return 0.0

    merged_df = pd.merge(forecast_df_full[['ds', 'yhat']], model.history[['ds', 'y']], on='ds', how='inner')
    merged_df.dropna(subset=['y', 'yhat'], inplace=True) 
    if merged_df.empty: return 0.0

    y_actual = merged_df['y'].astype(float)
    y_hat_hist = merged_df['yhat'].astype(float)
    
    non_zero_actuals_mask = (y_actual != 0)
    if non_zero_actuals_mask.sum() == 0:
        return 100.0 if (y_hat_hist == 0).all() else 0.0

    errors = abs(y_hat_hist - y_actual)
    percentage_errors = errors[non_zero_actuals_mask] / y_actual[non_zero_actuals_mask]
    mape = percentage_errors.mean() * 100
    
    accuracy = 100.0 - mape if not pd.isna(mape) else 0.0
    return round(max(0.0, min(100.0, accuracy)), 2)

def get_weekly_trend(forecast_df_full):
    if 'yhat' not in forecast_df_full.columns or len(forecast_df_full) < 14 : return 'N/A'
    forecast_df_full['yhat'] = pd.to_numeric(forecast_df_full['yhat'], errors='coerce')
    forecast_df_full.dropna(subset=['yhat'], inplace=True)

    if len(forecast_df_full) < 14: return 'N/A'
    last_week_yhat = forecast_df_full.tail(7)['yhat']
    prev_week_yhat = forecast_df_full.tail(14).head(7)['yhat']
    last_mean = last_week_yhat.mean()
    prev_mean = prev_week_yhat.mean()

    if pd.isna(last_mean) or pd.isna(prev_mean): return 'N/A'
    if prev_mean == 0:
        return '+0.00%' if last_mean == 0 else ('+100.00%' if last_mean > 0 else '-100.00%')
    
    delta = ((last_mean - prev_mean) / abs(prev_mean)) * 100 
    return f"{'+' if delta >= 0 else ''}{round(delta, 2)}%"

def get_table_info(category_param):
    config = CATEGORY_CONFIG.get(category_param, CATEGORY_CONFIG['emotion'])
    return config['table_name'], config['column_name']

# ==========================================
# --- 2. API ENDPOINTS (DATABASE) ---
# ==========================================

@app.route('/api/summary', methods=['GET', 'OPTIONS'])
def db_summary():
    if request.method == 'OPTIONS': return '', 200
    
    category = request.args.get('category', 'emotion')
    table_name, col_name = get_table_info(category)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Detected Today (Standard)
        cursor.execute(f"SELECT COUNT(id) AS count FROM {table_name} WHERE DATE(timestamp) = CURDATE()")
        detected_count = cursor.fetchone()['count'] or 0

        # 2. Dominant Item Today
        query_dominant = f"""
            SELECT {col_name} as item FROM (
                SELECT {col_name}, COUNT(id) AS count FROM {table_name}
                WHERE DATE(timestamp) = CURDATE()
                GROUP BY {col_name}
                ORDER BY count DESC
                LIMIT 1
            ) AS t
        """
        cursor.execute(query_dominant)
        row = cursor.fetchone()
        dominant_item = row['item'] if row else 'N/A'

        # 3. Weekly Stats
        cursor.execute(f"SELECT COUNT(id) AS total FROM {table_name} WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1)")
        total_this_week = cursor.fetchone()['total'] or 1
        
        cursor.execute(f"SELECT COUNT(id) AS total FROM {table_name} WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE() - INTERVAL 7 DAY, 1)")
        total_last_week = cursor.fetchone()['total'] or 1

        cursor.execute(f"SELECT {col_name} as item, COUNT(id) AS count FROM {table_name} WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1) GROUP BY {col_name}")
        this_week = {r['item']: (r['count'] / total_this_week) * 100 for r in cursor.fetchall()}

        cursor.execute(f"SELECT {col_name} as item, COUNT(id) AS count FROM {table_name} WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE() - INTERVAL 7 DAY, 1) GROUP BY {col_name}")
        last_week = {r['item']: (r['count'] / total_last_week) * 100 for r in cursor.fetchall()}

        changes = {}
        all_items = set(this_week.keys()).union(last_week.keys())
        for item in all_items:
            current = this_week.get(item, 0.0)
            last = last_week.get(item, 0.0)
            changes[item] = round(((current - last) / last) * 100, 2) if last != 0 else (100.0 if current > 0 else 0.0)
        
        return jsonify({
            'category': category,
            'detected_count': detected_count,
            'dominant_item': dominant_item,
            'weekly_changes': changes
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()


@app.route('/api/distribution', methods=['GET', 'OPTIONS'])
def db_distribution():
    if request.method == 'OPTIONS': return '', 200

    category = request.args.get('category', 'emotion')
    table_name, col_name = get_table_info(category)
    range_param = request.args.get('range', 'today')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if range_param == 'today':
            condition = "DATE(timestamp) = CURDATE()"
        elif range_param == 'week':
            condition = "YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1)"
        elif range_param == 'month':
            condition = "YEAR(timestamp) = YEAR(CURDATE()) AND MONTH(timestamp) = MONTH(CURDATE())"
        else:
            condition = "1=1"

        # Pake COUNT(id)
        query = f"""
            SELECT {col_name} AS label, COUNT(id) AS count
            FROM {table_name}
            WHERE {condition}
            GROUP BY {col_name}
        """

        cursor.execute(query)
        data = cursor.fetchall()

        return jsonify([{"emotion": r["label"], "count": r["count"]} for r in data])

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()


@app.route('/api/logs', methods=['GET', 'OPTIONS'])
def db_logs():
    """ 
    LOGS BERDASARKAN ID TERBARU 
    Menggunakan ORDER BY id DESC (Urut dari ID terbesar ke terkecil)
    """
    if request.method == 'OPTIONS': return '', 200

    category = request.args.get('category', 'emotion')
    table_name, col_name = get_table_info(category)

    conn = None
    try:
        conn = get_db_connection()
        
        # Select Kolom
        query_cols = f"id, timestamp, {col_name} AS label, confidence"
        if category == 'emotion': query_cols += ", user_id"

        # === FIX: ORDER BY id DESC ===
        query = f"""
            SELECT {query_cols}
            FROM {table_name}
            WHERE DATE(timestamp) = CURDATE()
            ORDER BY id DESC
            LIMIT 50
        """

        df = pd.read_sql(query, conn)

        if not df.empty:
            # Format Timestamp untuk display saja
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            df.fillna(value=pd.NA, inplace=True)
            records = [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in df.to_dict(orient='records')]
            return jsonify(records)

        return jsonify([])

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()


@app.route('/api/trends/today', methods=['GET', 'OPTIONS'])
def db_trends_today():
    """ 
    HOURLY CHART (THE FIX IS HERE)
    Kita paksa ambil jam WIB (UTC+7) langsung dari SQL.
    Jadi kalau di UTC jam 8, outputnya langsung 15 (Jam 3 Sore).
    """
    if request.method == 'OPTIONS': return '', 200
    category = request.args.get('category', 'emotion')
    table_name, col_name = get_table_info(category)
    
    conn = None
    try:
        conn = get_db_connection()
        
        # PERHATIKAN: HOUR(timestamp + INTERVAL 7 HOUR)
        query = f"""
            SELECT {col_name} as label, 
                   HOUR(timestamp - INTERVAL 7 HOUR) as hour, 
                   COUNT(id) as count
            FROM {table_name} 
            WHERE DATE(timestamp - INTERVAL 7 HOUR) = DATE(NOW() - INTERVAL 7 HOUR)
            GROUP BY label, hour 
            ORDER BY hour
        """
        df = pd.read_sql(query, conn)
        result = {}
        if not df.empty:
            for label_val, group in df.groupby('label'):
                result[label_val] = {'hours': group['hour'].tolist(), 'counts': group['count'].tolist()}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()


@app.route('/api/trends/weekly', methods=['GET', 'OPTIONS'])
def db_trends_weekly():
    if request.method == 'OPTIONS': return '', 200
    category = request.args.get('category', 'emotion')
    table_name, col_name = get_table_info(category)

    conn = None
    try:
        conn = get_db_connection()
        query = f"""
            SELECT {col_name} as label, WEEKDAY(timestamp) as day_of_week, COUNT(id) as count
            FROM {table_name} 
            WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1)
            GROUP BY label, day_of_week 
            ORDER BY day_of_week
        """
        df = pd.read_sql(query, conn)
        result = {}
        if not df.empty:
            for val, group in df.groupby('label'):
                result[val] = {'days': group['day_of_week'].tolist(), 'counts': group['count'].tolist()}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/trends', methods=['GET', 'OPTIONS'])
def db_trends_all():
    if request.method == 'OPTIONS': return '', 200
    category = request.args.get('category', 'emotion')
    table_name, col_name = get_table_info(category)

    conn = None
    try:
        conn = get_db_connection()
        query = f"""
            SELECT {col_name} as label, DATE(timestamp) as date, COUNT(id) as count
            FROM {table_name} GROUP BY label, DATE(timestamp) ORDER BY date
        """
        df = pd.read_sql(query, conn)
        result = {}
        if not df.empty:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            for val, group in df.groupby('label'):
                result[val] = {'dates': group['date'].tolist(), 'counts': group['count'].tolist()}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()


# ==========================================
# --- 3. FORECAST ENDPOINTS ---
# ==========================================

@app.route('/api/forecast', methods=['POST', 'OPTIONS'])
def get_forecast_data():
    if request.method == 'OPTIONS': return '', 200 
    try:
        payload = request.get_json()
        if not payload: return jsonify({"error": "Invalid payload"}), 400
        requested_item = payload.get('label') or payload.get('emotion') or 'happy'
        
        if requested_item not in MODELS: 
            return jsonify({"error": f"Model '{requested_item}' not found"}), 404
            
        model = MODELS[requested_item]
        if not hasattr(model, 'history') or model.history.empty: 
             return jsonify({'forecast_points': [], 'accuracy': 0.0, 'trend': 'N/A', 'label': requested_item, 'message': "No history data."}), 200

        forecast_days_count = int(payload.get('forecast_days', 7))
        granularity = payload.get('granularity', 'daily').lower()
        prophet_freq = {"hourly": "H", "daily": "D", "weekly": "W", "monthly": "M"}.get(granularity, 'D')
        
        future_df = model.make_future_dataframe(periods=forecast_days_count, freq=prophet_freq)
        forecast_df_full = model.predict(future_df)
        
        output_df = pd.merge(forecast_df_full[['ds', 'yhat', 'yhat_lower', 'yhat_upper']], 
                             model.history[['ds', 'y']], on='ds', how='left')

        recharts_data = []
        if not output_df.empty:
            df_chart = output_df.rename(columns={'y': 'actual', 'ds': 'name'})
            df_chart['name'] = pd.to_datetime(df_chart['name']).dt.strftime('%Y-%m-%d')
            raw_records = df_chart.to_dict(orient='records')
            for r in raw_records:
                clean_r = {}
                for k, v in r.items():
                    if (isinstance(v, float) and math.isnan(v)) or pd.isna(v): clean_r[k] = None 
                    else: clean_r[k] = v
                recharts_data.append(clean_r)
        
        return jsonify({
            'forecast_points': recharts_data,
            'accuracy': get_forecast_accuracy(model, forecast_df_full),
            'trend': get_weekly_trend(forecast_df_full),
            'label': requested_item,
            'forecast_days': forecast_days_count
        })
    except Exception as e:
        app.logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/forecast_summary', methods=['GET', 'OPTIONS'])
def api_forecast_summary():
    if request.method == 'OPTIONS': return '', 200 
    accuracies, trends = {}, {}
    for name, model in MODELS.items():
        try:
            if not hasattr(model, 'history') or model.history.empty:
                accuracies[name], trends[name] = 0.0, "N/A"
                continue
            future = model.make_future_dataframe(periods=7, freq='D')
            forecast = model.predict(future)
            accuracies[name] = get_forecast_accuracy(model, forecast)
            trends[name] = get_weekly_trend(forecast)
        except Exception:
            accuracies[name], trends[name] = 0.0, "Error"
    return jsonify({"accuracies": accuracies, "trends": trends})

@app.route('/api/forecast_trends_today', methods=['GET', 'OPTIONS'])
def api_forecast_trends_today():
    if request.method == 'OPTIONS': return '', 200
    daily_trends = {}
    for name, model in MODELS.items():
        try:
            if not hasattr(model, 'history') or model.history.empty:
                daily_trends[name] = "N/A"
                continue
            future = model.make_future_dataframe(periods=30, freq='D') 
            forecast = model.predict(future)
            if len(forecast) >= 2:
                today_yhat = forecast.iloc[-1]['yhat']
                yesterday_yhat = forecast.iloc[-2]['yhat']
                if yesterday_yhat == 0: daily_trends[name] = '+0.00%'
                else:
                    delta = ((today_yhat - yesterday_yhat) / abs(yesterday_yhat)) * 100
                    daily_trends[name] = f"{'+' if delta >= 0 else ''}{round(delta, 2)}%"
            else: daily_trends[name] = "N/A"
        except Exception:
            daily_trends[name] = "Error"
    return jsonify(daily_trends)

@app.route('/api/forecast_distribution', methods=['GET', 'OPTIONS'])
def api_forecast_distribution():
    if request.method == 'OPTIONS': return '', 200
    time_range_param = request.args.get('range', 'today')
    end_date = datetime.now()
    if time_range_param == 'week': start_date = end_date - timedelta(days=7)
    elif time_range_param == 'month': start_date = end_date - timedelta(days=30)
    else: start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

    distribution_result = []
    for name, model in MODELS.items():
        try:
            if not hasattr(model, 'history') or model.history.empty:
                distribution_result.append({"emotion": name, "count": 0})
                continue
            df = model.history.copy()
            df['ds'] = pd.to_datetime(df['ds']).dt.tz_localize(None)
            mask = (df['ds'] >= start_date) & (df['ds'] <= end_date)
            count = df.loc[mask, 'y'].sum()
            distribution_result.append({"emotion": name, "count": int(count)})
        except Exception:
            distribution_result.append({"emotion": name, "count": 0})
    return jsonify(distribution_result)

@app.route('/api/forecast_logs', methods=['GET', 'OPTIONS'])
def get_forecast_api_logs():
    if request.method == 'OPTIONS': return '', 200
    return jsonify(list(FORECAST_API_LOGS))

# --- Main Entry Point ---
if __name__ == '__main__':
    try:
        conn = get_db_connection()
        if conn: print("DB Connected Successfully"); conn.close()
    except Exception as e: print(f"DB Connection Failed: {e}")
    app.run(debug=True, port=5000, host='0.0.0.0')