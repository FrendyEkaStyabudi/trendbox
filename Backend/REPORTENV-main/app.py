from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import mysql.connector
import pandas as pd
from datetime import datetime, timezone
import logging
import os
import io

# --- Inisialisasi Aplikasi Flask ---
app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# --- Konfigurasi CORS Global ---
origins_env = os.getenv("FRONTEND_ORIGINS", "*")
origins = "*" if origins_env.strip() == "*" else [origin.strip() for origin in origins_env.split(",") if origin.strip()]
CORS(app, supports_credentials=True, origins=origins)

# --- Konfigurasi Database ---
DB_CONFIG = {
    'user': os.getenv('DB_USER', 'trendbox-app'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_DATABASE', os.getenv('DB_NAME', 'trendbox')),
}

instance_connection_name = os.getenv('INSTANCE_CONNECTION_NAME', '').strip()
if instance_connection_name:
    DB_CONFIG['unix_socket'] = f"/cloudsql/{instance_connection_name}"
else:
    DB_CONFIG['host'] = os.getenv('DB_HOST', '127.0.0.1')
    DB_CONFIG['port'] = int(os.getenv('DB_PORT', '3306'))

@app.get('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'reports-api'})

# --- Fungsi Bantuan Database ---
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        app.logger.info("Database connection successful.")
        return conn
    except mysql.connector.Error as err:
        app.logger.error(f"Error connecting to database: {err}")
        raise

def get_report_data(start_date, end_date, emotions):
    conn = None
    try:
        conn = get_db_connection()
        
        query = "SELECT timestamp, emotion FROM emotion_track WHERE DATE(timestamp) BETWEEN DATE(%s) AND DATE(%s)"
        params = [start_date, end_date]

        if emotions:
            emotion_placeholders = ', '.join(['%s'] * len(emotions))
            query += f" AND emotion IN ({emotion_placeholders})"
            params.extend(emotions)
        
        app.logger.info(f"Executing query with {len(params)} parameters.")
        df = pd.read_sql(query, conn, params=params)
        app.logger.info(f"Successfully fetched {len(df)} records for the report.")
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df

    except mysql.connector.Error as db_err:
        app.logger.error(f"Database error in get_report_data: {db_err}", exc_info=True)
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()

def get_attribute_data(start_date, end_date):
    conn = None
    try:
        conn = get_db_connection()
        query = """
            SELECT timestamp, 'head' AS attribute_type, label
            FROM head_track
            WHERE DATE(timestamp) BETWEEN DATE(%s) AND DATE(%s)
            UNION ALL
            SELECT timestamp, 'clothing' AS attribute_type, label
            FROM clothing_track
            WHERE DATE(timestamp) BETWEEN DATE(%s) AND DATE(%s)
        """
        params = [start_date, end_date, start_date, end_date]
        df = pd.read_sql(query, conn, params=params)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        app.logger.info(f"Successfully fetched {len(df)} attribute records for the report.")
        return df
    except mysql.connector.Error as db_err:
        app.logger.error(f"Database error in get_attribute_data: {db_err}", exc_info=True)
        return pd.DataFrame(columns=['timestamp', 'attribute_type', 'label'])
    finally:
        if conn and conn.is_connected():
            conn.close()

# --- Fungsi Pemrosesan Data ---
def process_charts_data(df):
    if df.empty: return {"emotionTrends": {"categories": [], "series": []}}
    df_trends = df.copy()
    # Sintaks resample yang sudah diperbaiki untuk menghindari FutureWarning
    trends_data = df_trends.groupby('emotion').resample('D', on='timestamp').size().unstack(level=0, fill_value=0)
    
    return {
        "emotionTrends": {
            "categories": trends_data.index.strftime('%Y-%m-%d').tolist(),
            "series": [{"name": str(emotion), "data": data.tolist()} for emotion, data in trends_data.items()]
        }
    }

def process_table_data(df):
    if df.empty: return []
    df_table = df.copy()
    daily_summary = df_table.set_index('timestamp').groupby([pd.Grouper(freq='D'), 'emotion']).size().unstack(fill_value=0)
    all_emotions_in_data = df['emotion'].unique().tolist()
    for emotion in all_emotions_in_data:
        if emotion not in daily_summary.columns: daily_summary[emotion] = 0
    daily_summary = daily_summary.reset_index()
    daily_summary['date'] = daily_summary['timestamp'].dt.strftime('%b %d, %Y')
    final_columns = ['date'] + all_emotions_in_data
    daily_summary = daily_summary[final_columns]
    return daily_summary.to_dict(orient='records')

def process_attribute_data(attribute_df):
    result = {"head": [], "clothing": []}
    if attribute_df.empty:
        return result
    grouped = attribute_df.groupby(['attribute_type', 'label']).size().reset_index(name='count')
    for attribute_type in result:
        subset = grouped[grouped['attribute_type'] == attribute_type].sort_values(
            ['count', 'label'], ascending=[False, True]
        )
        result[attribute_type] = [
            {"label": str(row['label']), "count": int(row['count'])}
            for _, row in subset.iterrows()
        ]
    return result

def generate_ai_insights(df, attribute_df):
    if df.empty and attribute_df.empty:
        return [{"badge": "Info", "color": "blue", "title": "No Data Available", "description": "No emotion or attribute data was found for the selected filters."}]
    insights = []
    if not df.empty:
        dominant_emotion = df['emotion'].mode()[0]
        insights.append({"badge": "Dominant Emotion", "color": "blue", "title": f"{dominant_emotion.capitalize()} was the most common emotion.","description": "This emotion appeared most frequently in the selected time period."})
        if 'happy' in df['emotion'].unique():
            peak_happy_day = df[df['emotion'] == 'happy']['timestamp'].dt.date.mode()[0]
            insights.append({"badge": "Positive Trend", "color": "green", "title": "Peak Happiness Day","description": f"The highest number of 'happy' expressions were detected on {peak_happy_day.strftime('%B %d, %Y')}."})

    attribute_distribution = process_attribute_data(attribute_df)
    if attribute_distribution['head']:
        dominant_head = attribute_distribution['head'][0]
        insights.append({
            "badge": "Head Attribute",
            "color": "orange",
            "title": f"{dominant_head['label'].replace('_', ' ').title()} was the most common head attribute.",
            "description": f"It was detected {dominant_head['count']} times in the selected period.",
        })
    if attribute_distribution['clothing']:
        dominant_clothing = attribute_distribution['clothing'][0]
        insights.append({
            "badge": "Clothing Attribute",
            "color": "teal",
            "title": f"{dominant_clothing['label'].replace('_', ' ').title()} was the most common clothing attribute.",
            "description": f"It was detected {dominant_clothing['count']} times in the selected period.",
        })
    if not df.empty:
        insights.append({"badge": "Recommendation", "color": "purple", "title": "Suggested Action Items","description": "Compare emotion peaks with clothing and head attributes to identify useful visitor patterns."})
    return insights

# --- API Endpoints ---
@app.route('/api/distribution', methods=['GET'])
def db_distribution():
    conn = None
    try:
        range_param = request.args.get('range', 'today')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        condition_map = {
            'today': "DATE(timestamp) = CURDATE()",
            'week': "YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1)",
            'month': "YEAR(timestamp) = YEAR(CURDATE()) AND MONTH(timestamp) = MONTH(CURDATE())"
        }
        condition = condition_map.get(range_param, "DATE(timestamp) = CURDATE()")
        query = f"SELECT emotion, COUNT(*) AS count FROM emotion_track WHERE {condition} GROUP BY emotion"
        cursor.execute(query)
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Error in /api/distribution: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/export', methods=['POST'])
def export_report():
    try:
        config = request.get_json()
        if not config: return jsonify({"error": "Invalid JSON payload"}), 400
        date_range = config.get('dateRange', {}); start_date_str = date_range.get('start'); end_date_str = date_range.get('end'); emotions = config.get('emotions', [])
        if not all([start_date_str, end_date_str]): return jsonify({"error": "Start and end dates are required."}), 400
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')); end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        master_df = get_report_data(start_date, end_date, emotions)
        if master_df.empty: return jsonify({"error": "No data to export"}), 404
        table_data = process_table_data(master_df); export_df = pd.DataFrame(table_data)
        csv_buffer = io.StringIO(); export_df.to_csv(csv_buffer, index=False); csv_buffer.seek(0)
        return Response(csv_buffer.getvalue(), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=emotion_report.csv"})
    except Exception as e:
        app.logger.error(f"An unexpected error occurred in /api/export: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500

@app.route('/api/reports', methods=['POST'])
def generate_report():
    try:
        config = request.get_json()
        if not config: return jsonify({"error": "Invalid JSON payload"}), 400
        report_type = config.get('reportType', 'detailed'); date_range = config.get('dateRange', {}); start_date_str = date_range.get('start'); end_date_str = date_range.get('end'); emotions = config.get('emotions', [])
        if not all([start_date_str, end_date_str]): return jsonify({"error": "Start and end dates are required."}), 400
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')); end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        master_df = get_report_data(start_date, end_date, emotions)
        attribute_df = get_attribute_data(start_date, end_date)
        charts_data, table_data, insights_data = {}, {}, {}
        attribute_data = process_attribute_data(attribute_df)
        
        if report_type == 'summary':
            insights_data = generate_ai_insights(master_df, attribute_df)
        elif report_type == 'trends':
            charts_data = process_charts_data(master_df)
            charts_data['attributeDistribution'] = attribute_data
        else: # Default ke 'detailed'
             charts_data = process_charts_data(master_df)
             charts_data['attributeDistribution'] = attribute_data
             table_data = process_table_data(master_df)
             insights_data = generate_ai_insights(master_df, attribute_df)
             
        attribute_table = [
            {"type": attribute_type, "label": item['label'], "count": item['count']}
            for attribute_type, items in attribute_data.items()
            for item in items
        ]
        response_payload = {"reportMetadata": {"reportTitle": f"{report_type.capitalize()} Report", "dateRangeFormatted": f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}", "generatedAt": datetime.now(timezone.utc).isoformat()}, "charts": charts_data, "tables": {"dailySummary": table_data, "attributeSummary": attribute_table}, "insights": insights_data}
        return jsonify(response_payload)
    except Exception as e:
        app.logger.error(f"An unexpected error occurred in /api/reports: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500

if __name__ == '__main__':
    print("--- Emotion Insights & Reports API ---")
    app.run(debug=True, port=int(os.getenv('PORT', '5002')), host='0.0.0.0')

