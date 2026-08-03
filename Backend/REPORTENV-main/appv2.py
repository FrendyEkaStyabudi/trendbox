from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import mysql.connector
import pandas as pd
from datetime import datetime, timezone
import logging
import os
import io
import json
import requests

# ============================================================
# Flask init & CORS
# ============================================================

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

CORS(app, supports_credentials=True, origins=["http://localhost:3000"])

# ============================================================
# DB CONFIG
# ============================================================

DB_CONFIG = {
    'host': 'yamanote.proxy.rlwy.net',
    'user': 'root',
    'password': 'rgjPtKwPcPlbBrZJOeAFSeQgAjULowPu',
    'database': 'railway',
    'port': 59862,
    'connect_timeout': 10
}

# Tabel meta dinamis
TABLE_METADATA = {
    'emotion_track': {
        'category_col': 'emotion',
        'filter_key': 'emotions',
        'title': 'Emotion'
    },
    'clothing_track': {
        'category_col': 'label',
        'filter_key': 'labels',
        'title': 'Clothing'
    },
    'head_track': {
        'category_col': 'label',
        'filter_key': 'labels',
        'title': 'Headwear'
    }
}

# ============================================================
# Groq Config (pakai ENV atau fallback placeholder)
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "llama-3.1-8b-instant")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


# ============================================================
# DB HELPER
# ============================================================

def get_db_connection():
    """Open MySQL connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        app.logger.error(f"DB connection error: {err}")
        raise


# ============================================================
# DATA FETCHER (tanpa read_sql)
# ============================================================

def get_report_data(table_name: str, category_column: str,
                    start_date: datetime, end_date: datetime,
                    categories: list) -> pd.DataFrame:
    """
    Ambil data dari table tertentu dengan filter tanggal + kategori (opsional).
    Return: DataFrame dengan kolom ['timestamp', category_column]
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = (
            f"SELECT timestamp, {category_column} "
            f"FROM {table_name} "
            "WHERE DATE(timestamp) BETWEEN DATE(%s) AND DATE(%s)"
        )
        params = [start_date.strftime('%Y-%m-%d'),
                  end_date.strftime('%Y-%m-%d')]

        if categories:
            placeholders = ", ".join(["%s"] * len(categories))
            query += f" AND {category_column} IN ({placeholders})"
            params.extend(categories)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        df = pd.DataFrame(rows)

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        return df

    except Exception as e:
        app.logger.error(f"get_report_data error: {e}", exc_info=True)
        return pd.DataFrame()

    finally:
        if conn and conn.is_connected():
            conn.close()


# ============================================================
# CHART PROCESSOR (FIXED)
# ============================================================

def process_charts_data(df: pd.DataFrame, category_column: str):
    """
    Menghasilkan struktur data tren harian.
    FIX: aman untuk kasus single-category (tidak MultiIndex).
    """
    if df.empty:
        return {"trends": {"categories": [], "series": []}}

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Group + resample
    grouped = (
        df.set_index("timestamp")
          .groupby(category_column)
          .resample("D")
          .size()
    )

    # CASE 1 → hasil MultiIndex (normal)
    if isinstance(grouped.index, pd.MultiIndex):
        trends = grouped.unstack(level=0, fill_value=0)

    # CASE 2 → hasil DatetimeIndex (hanya 1 kategori tersisa)
    else:
        tmp = grouped.reset_index()
        tmp.columns = ["timestamp", category_column, "count"]
        trends = tmp.pivot(index="timestamp",
                           columns=category_column,
                           values="count").fillna(0)

    # Format output
    trends = trends.reset_index()
    categories = trends["timestamp"].dt.strftime("%Y-%m-%d").tolist()

    series = []
    for col in trends.columns:
        if col == "timestamp":
            continue
        series.append({
            "name": col,
            "data": trends[col].astype(int).tolist()
        })

    return {
        "trends": {
            "categories": categories,
            "series": series
        }
    }


# ============================================================
# TABLE PROCESSOR
# ============================================================

def process_table_data(df: pd.DataFrame, category_column: str):
    """
    Merangkum data per hari per kategori jadi bentuk tabular.
    """
    if df.empty:
        return []

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    daily = (
        df.set_index("timestamp")
          .groupby([pd.Grouper(freq="D"), category_column])
          .size()
          .unstack(fill_value=0)
    )

    daily = daily.reset_index()
    daily["date"] = daily["timestamp"].dt.strftime("%b %d, %Y")
    daily = daily.drop(columns=["timestamp"])

    return daily.to_dict(orient="records")


# ============================================================
# BASIC INSIGHTS (tanpa LLM)
# ============================================================

def generate_ai_insights(df: pd.DataFrame, category_column: str):
    """
    Insight sederhana (dominant category).
    """
    if df.empty:
        return [{
            "badge": "Info",
            "color": "gray",
            "title": "No Data",
            "description": "No activity detected in the selected time range."
        }]

    dominant = df[category_column].mode()[0]
    counts = df[category_column].value_counts().to_dict()

    return [
        {
            "badge": "Dominant",
            "color": "blue",
            "title": f"Most frequent: {dominant}",
            "description": f"'{dominant}' appears the most in the selected range."
        },
        {
            "badge": "Distribution",
            "color": "purple",
            "title": "Category distribution",
            "description": f"Frequency per category: {counts}"
        }
    ]


# ============================================================
# GROQ INSIGHT (LLM)
# ============================================================

def generate_groq_insight(df: pd.DataFrame, category_column: str):
    """
    Mengirim ringkasan data ke Groq untuk dibuatkan insight.
    Return list of insight dict sama format dengan generate_ai_insights.
    """
    if df.empty:
        return []

    if not GROQ_API_KEY or GROQ_API_KEY == "YOUR_GROQ_API_KEY_HERE":
        # Groq belum dikonfigurasi
        return [{
            "badge": "AI",
            "color": "orange",
            "title": "Groq not configured",
            "description": "Set GROQ_API_KEY in environment to enable AI-generated insights."
        }]

    # Ringkas data: hitung frekuensi per kategori
    counts = df[category_column].value_counts().to_dict()

    prompt = f"""
You are an analytics assistant. The data is aggregated as category counts.

Category column: {category_column}
Counts:
{json.dumps(counts, indent=2)}

Generate 2-3 short, business-style insights.
Respond ONLY with a JSON array like:
[
  {{"badge": "...", "color": "...", "title": "...", "description": "..."}}
]
"""

    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": GROQ_MODEL_NAME,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # Parse JSON dari LLM
        insights = json.loads(content)
        if isinstance(insights, dict):
            insights = [insights]

        # fallback warna kalau kosong
        for ins in insights:
            ins.setdefault("badge", "AI Insight")
            ins.setdefault("color", "teal")
            ins.setdefault("title", "Insight")
            ins.setdefault("description", "")

        return insights

    except Exception as e:
        app.logger.error(f"Groq insight error: {e}", exc_info=True)
        return [{
            "badge": "AI Error",
            "color": "red",
            "title": "AI insight failed",
            "description": "Unable to generate AI insights at the moment."
        }]


# ============================================================
# CORRELATION INSIGHT (emotion ↔ clothing/head)
# ============================================================

def generate_correlation_insight(df: pd.DataFrame, category_column: str, table_name: str):
    """
    Memberikan insight korelasi antara clothing/head dengan emotion.
    - Untuk table clothing_track/head_track: join ke emotion_track berdasarkan timestamp terdekat.
    - Untuk emotion_track sendiri: tidak menghasilkan apa-apa.
    """
    try:
        if table_name == "emotion_track" or df.empty:
            return []

        # Ambil emotion_track terpisah
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT timestamp, emotion FROM emotion_track")
        emo_rows = cursor.fetchall()
        conn.close()

        emo_df = pd.DataFrame(emo_rows)
        if emo_df.empty:
            return []

        emo_df["timestamp"] = pd.to_datetime(emo_df["timestamp"])
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Merge berdasarkan timestamp terdekat (toleransi 3 detik)
        merged = pd.merge_asof(
            df.sort_values("timestamp"),
            emo_df.sort_values("timestamp"),
            on="timestamp",
            direction="nearest",
            tolerance=pd.Timedelta("3s")
        )

        if merged.empty or merged["emotion"].isna().all():
            return []

        combo = (
            merged
            .dropna(subset=["emotion"])
            .groupby([category_column, "emotion"])
            .size()
            .reset_index(name="count")
        )

        if combo.empty:
            return []

        combo = combo.sort_values("count", ascending=False).head(1)

        item = combo.iloc[0][category_column]
        emotion = combo.iloc[0]["emotion"]
        count = int(combo.iloc[0]["count"])

        return [{
            "badge": "Correlation",
            "color": "teal",
            "title": f"Pattern: {item} ↔ {emotion}",
            "description": (
                f"Items with label '{item}' most frequently appear together "
                f"with '{emotion}' emotion ({count} matched events)."
            )
        }]

    except Exception as e:
        app.logger.error(f"Correlation insight error: {e}", exc_info=True)
        return []


# ============================================================
# ENDPOINT: DISTRIBUTION
# ============================================================

@app.route("/api/distribution", methods=["GET"])
def distribution():
    """
    Mengembalikan distribusi kategori per tabel:
    GET /api/distribution?range=today|week|month&table=emotion_track|clothing_track|head_track
    """
    conn = None
    try:
        range_param = request.args.get("range", "today")
        table_name = request.args.get("table", "emotion_track")

        meta = TABLE_METADATA.get(table_name)
        if not meta:
            return jsonify({"error": f"Table '{table_name}' not supported"}), 400

        category_column = meta["category_col"]

        condition_map = {
            "today": "DATE(timestamp) = CURDATE()",
            "week": "YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1)",
            "month": "YEAR(timestamp) = YEAR(CURDATE()) AND MONTH(timestamp) = MONTH(CURDATE())"
        }
        condition = condition_map.get(range_param, condition_map["today"])

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = (
            f"SELECT {category_column} AS category, COUNT(*) AS count "
            f"FROM {table_name} "
            f"WHERE {condition} "
            f"GROUP BY {category_column}"
        )

        cursor.execute(query)
        rows = cursor.fetchall()

        return jsonify(rows)

    except Exception as e:
        app.logger.error(f"/api/distribution error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

    finally:
        if conn and conn.is_connected():
            conn.close()


# ============================================================
# ENDPOINT: EXPORT CSV
# ============================================================

@app.route("/api/export", methods=["POST"])
def export_report():
    try:
        cfg = request.get_json()
        if not cfg:
            return jsonify({"error": "Invalid JSON payload"}), 400

        table_name = cfg.get("table", "emotion_track")
        meta = TABLE_METADATA.get(table_name)
        if not meta:
            return jsonify({"error": f"Table '{table_name}' not supported"}), 400

        category_column = meta["category_col"]
        filter_key = meta["filter_key"]

        date_range = cfg.get("dateRange", {})
        start_str = date_range.get("start")
        end_str = date_range.get("end")

        if not start_str or not end_str:
            return jsonify({"error": "Start and end dates are required"}), 400

        start_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        categories = cfg.get(filter_key, [])

        df = get_report_data(table_name, category_column, start_date, end_date, categories)
        if df.empty:
            return jsonify({"error": f"No {meta['title']} data found to export"}), 404

        table_data = process_table_data(df, category_column)
        export_df = pd.DataFrame(table_data)

        csv_buffer = io.StringIO()
        export_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        filename = f"{table_name}_report.csv"
        return Response(
            csv_buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        app.logger.error(f"/api/export error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ============================================================
# ENDPOINT: REPORTS (MAIN)
# ============================================================

@app.route("/api/reports", methods=["POST"])
def generate_report():
    try:
        cfg = request.get_json()
        if not cfg:
            return jsonify({"error": "Invalid JSON payload"}), 400

        table_name = cfg.get("table", "emotion_track")
        meta = TABLE_METADATA.get(table_name)
        if not meta:
            return jsonify({"error": f"Table '{table_name}' not supported"}), 400

        category_column = meta["category_col"]
        filter_key = meta["filter_key"]
        table_title = meta["title"]

        date_range = cfg.get("dateRange", {})
        start_str = date_range.get("start")
        end_str = date_range.get("end")

        if not start_str or not end_str:
            return jsonify({"error": "Start and end dates are required"}), 400

        start_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        categories = cfg.get(filter_key, [])

        df = get_report_data(table_name, category_column, start_date, end_date, categories)

        charts_data = process_charts_data(df, category_column)
        table_data = process_table_data(df, category_column)

        # Basic insight
        insights = generate_ai_insights(df, category_column)
        # Groq insight
        insights.extend(generate_groq_insight(df, category_column))
        # Correlation insight (emotion ↔ clothing/head)
        insights.extend(generate_correlation_insight(df, category_column, table_name))

        payload = {
            "reportMetadata": {
                "reportTitle": f"{table_title} Detailed Report",
                "dateRangeFormatted": f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}",
                "trackedItem": category_column,
                "generatedAt": datetime.now(timezone.utc).isoformat()
            },
            "charts": charts_data,
            "tables": {"dailySummary": table_data},
            "insights": insights
        }

        return jsonify(payload)

    except Exception as e:
        app.logger.error(f"/api/reports error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ============================================================
# ENDPOINT: CATEGORIES
# ============================================================

@app.route("/api/categories", methods=["GET"])
def get_categories():
    conn = None
    try:
        table_name = request.args.get("table")
        meta = TABLE_METADATA.get(table_name)
        if not meta:
            return jsonify({"error": "Unsupported table"}), 400

        category_column = meta["category_col"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(f"SELECT DISTINCT {category_column} FROM {table_name}")
        rows = cursor.fetchall()

        categories = [row[0] for row in rows]

        return jsonify({
            "table": table_name,
            "category_column": category_column,
            "categories": categories
        })

    except Exception as e:
        app.logger.error(f"/api/categories error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

    finally:
        if conn and conn.is_connected():
            conn.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    print("🚀 General Tracking + Groq + Correlation Insights API running on port 5002")
    app.run(debug=True, port=5002, host="0.0.0.0")
