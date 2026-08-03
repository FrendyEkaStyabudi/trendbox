"""
attribute_queries.py

SQL query helpers for attribute tables (`clothing_track`, `head_track`) mirroring the
emotion queries in `app.py` and `tess.py`.

Functions accept a DB connection and table name and return Python dicts/lists suitable
for use in an API or CLI.
"""
from typing import Dict, List, Any
import mysql.connector
import pandas as pd
from datetime import datetime

def summary_today(conn: mysql.connector.MySQLConnection, table: str, label_col: str = 'label') -> Dict[str, Any]:
    cur = conn.cursor(dictionary=True)
    # Detected today
    cur.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE DATE(timestamp) = CURDATE()")
    detected_row = cur.fetchone()
    detected = detected_row['count'] if detected_row else 0

    # Dominant label today
    query_dom = f"""
        SELECT {label_col} FROM (
            SELECT {label_col}, COUNT(*) AS count FROM {table}
            WHERE DATE(timestamp) = CURDATE()
            GROUP BY {label_col}
            ORDER BY count DESC
            LIMIT 1
        ) AS t
    """
    cur.execute(query_dom)
    row = cur.fetchone()
    dominant = row[label_col] if row else 'N/A'

    # Weekly change (normalized proportions)
    cur.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE YEARWEEK(timestamp,1) = YEARWEEK(CURDATE(),1)")
    total_this_week_row = cur.fetchone()
    total_this_week = total_this_week_row['total'] if total_this_week_row and total_this_week_row['total'] else 1

    cur.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE YEARWEEK(timestamp,1) = YEARWEEK(CURDATE() - INTERVAL 7 DAY,1)")
    total_last_week_row = cur.fetchone()
    total_last_week = total_last_week_row['total'] if total_last_week_row and total_last_week_row['total'] else 1

    cur.execute(f"SELECT {label_col}, COUNT(*) AS count FROM {table} WHERE YEARWEEK(timestamp,1) = YEARWEEK(CURDATE(),1) GROUP BY {label_col}")
    this_week_counts = cur.fetchall()
    this_week = {r[label_col]: r['count']/total_this_week for r in this_week_counts}

    cur.execute(f"SELECT {label_col}, COUNT(*) AS count FROM {table} WHERE YEARWEEK(timestamp,1) = YEARWEEK(CURDATE() - INTERVAL 7 DAY,1) GROUP BY {label_col}")
    last_week_counts = cur.fetchall()
    last_week = {r[label_col]: r['count']/total_last_week for r in last_week_counts}

    changes = {}
    all_labels = set(this_week.keys()).union(last_week.keys())
    for lab in all_labels:
        current = this_week.get(lab, 0)
        last = last_week.get(lab, 0)
        if current == 0 and last == 0:
            changes[lab] = 0.0
        elif last == 0:
            changes[lab] = 100.0 if current > 0 else 0.0
        else:
            changes[lab] = round(((current - last) / last) * 100, 2)

    cur.close()
    return {'detected_today': detected, 'dominant_today': dominant, 'weekly_changes': changes}


def logs_latest(conn: mysql.connector.MySQLConnection, table: str, limit: int = 50) -> List[Dict[str, Any]]:
    # Return recent log rows with timestamp, label, confidence, source
    query = f"SELECT timestamp, label, confidence, source FROM {table} ORDER BY timestamp DESC LIMIT {int(limit)}"
    df = pd.read_sql(query, conn)
    if not df.empty:
        df['timestamp'] = df['timestamp'].astype(str)
        return df.to_dict(orient='records')
    return []


def distribution(conn: mysql.connector.MySQLConnection, table: str, range_param: str = 'today', label_col: str = 'label') -> List[Dict[str, Any]]:
    if range_param == 'today':
        condition = "DATE(timestamp) = CURDATE()"
    elif range_param == 'week':
        condition = "YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1)"
    elif range_param == 'month':
        condition = "YEAR(timestamp) = YEAR(CURDATE()) AND MONTH(timestamp) = MONTH(CURDATE())"
    else:
        condition = "1=1"

    sql = f"SELECT {label_col} as label, COUNT(*) as count FROM {table} WHERE {condition} GROUP BY {label_col}"
    cur = conn.cursor(dictionary=True)
    cur.execute(sql)
    data = cur.fetchall()
    cur.close()
    return data


def trends_today(conn: mysql.connector.MySQLConnection, table: str, label_col: str = 'label') -> Dict[str, Any]:
    df = pd.read_sql(f"SELECT {label_col} as label, HOUR(timestamp) as hour, COUNT(*) as count FROM {table} WHERE DATE(timestamp) = CURDATE() GROUP BY {label_col}, hour ORDER BY hour", conn)
    result = {}
    if not df.empty:
        for lab, group in df.groupby('label'):
            result[lab] = {'hours': group['hour'].tolist(), 'counts': group['count'].tolist()}
    return result


def trends_weekly(conn: mysql.connector.MySQLConnection, table: str, label_col: str = 'label') -> Dict[str, Any]:
    df = pd.read_sql(f"SELECT {label_col} as label, WEEKDAY(timestamp) as day_of_week, COUNT(*) as count FROM {table} WHERE YEARWEEK(timestamp, 1) = YEARWEEK(CURDATE(), 1) GROUP BY {label_col}, day_of_week ORDER BY day_of_week", conn)
    result = {}
    if not df.empty:
        for lab, group in df.groupby('label'):
            result[lab] = {'days': group['day_of_week'].tolist(), 'counts': group['count'].tolist()}
    return result


def trends(conn: mysql.connector.MySQLConnection, table: str, label_col: str = 'label') -> Dict[str, Any]:
    df = pd.read_sql(f"SELECT {label_col} as label, DATE(timestamp) as date, COUNT(*) as count FROM {table} GROUP BY {label_col}, DATE(timestamp) ORDER BY date", conn)
    result = {}
    if not df.empty:
        df['date'] = df['date'].astype(str)
        for lab, group in df.groupby('label'):
            result[lab] = {'dates': group['date'].tolist(), 'counts': group['count'].tolist()}
    return result


def run_queries_for_date(conn: mysql.connector.MySQLConnection, table: str, target_date: str, label_col: str = 'label'):
    """Run a set of queries for a specific date similar to `tess.run_queries_for_date`."""
    print(f"\n{'='*10} RESULTS FOR {table} ON {target_date} {'='*10}")
    cur = conn.cursor(dictionary=True)

    q_total = f"SELECT COUNT(*) AS count FROM {table} WHERE DATE(timestamp) = %s"
    cur.execute(q_total, (target_date,))
    rc = cur.fetchone()
    print('Total:', rc['count'] if rc else 0)

    q_dom = f"SELECT {label_col} FROM {table} WHERE DATE(timestamp) = %s GROUP BY {label_col} ORDER BY COUNT(*) DESC LIMIT 1"
    cur.execute(q_dom, (target_date,))
    dom = cur.fetchone()
    print('Dominant:', dom[label_col] if dom else 'N/A')

    q_dist = f"SELECT {label_col} as label, COUNT(*) as count FROM {table} WHERE DATE(timestamp) = %s GROUP BY {label_col}"
    df_dist = pd.read_sql(q_dist, conn, params=(target_date,))
    if df_dist.empty:
        print('No distribution data')
    else:
        print(df_dist.to_string(index=False))

    q_trend = f"SELECT {label_col} as label, HOUR(timestamp) as hour, COUNT(*) as count FROM {table} WHERE DATE(timestamp) = %s GROUP BY {label_col}, hour ORDER BY hour"
    df_trend = pd.read_sql(q_trend, conn, params=(target_date,))
    if df_trend.empty:
        print('No hourly trends')
    else:
        print(df_trend.to_string(index=False))

    cur.close()


if __name__ == '__main__':
    import os
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_DATABASE', ''),
        'port': int(os.getenv('DB_PORT', 3306)),
    }
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        # quick demo for both tables if available
        for t in ('clothing_track', 'head_track'):
            try:
                # run today's summary
                s = summary_today(conn, t)
                print('\nTable:', t, 'summary:', s)
            except Exception as e:
                print('Skipping', t, '->', e)
    finally:
        if conn and conn.is_connected():
            conn.close()
