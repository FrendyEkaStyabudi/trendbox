"""
inject_shifted_separate.py

Insert shifted CSVs into two separate tables:
 - data_baju_shifted.csv -> `clothing_track`
 - data_kepala_shifted.csv -> `head_track`

Does NOT insert CSV `id` column. Does NOT process fluktuasi files.
After insert, prints simple analysis (counts, date range, top labels).
"""
import os
import mysql.connector
import pandas as pd
from mysql.connector import errorcode
from datetime import datetime

from injectsqldataattribut import DB_CONFIG


TABLES = {
    'head_track': (
        "CREATE TABLE IF NOT EXISTS head_track ("
        "id INT NOT NULL AUTO_INCREMENT,"
        "label VARCHAR(255),"
        "confidence FLOAT,"
        "timestamp DATETIME,"
        "source VARCHAR(128),"
        "PRIMARY KEY (id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
    ),
}


def connect_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"DB connect error: {err}")
        raise


def create_tables(conn):
    cursor = conn.cursor()
    for name, ddl in TABLES.items():
        cursor.execute(ddl)
    cursor.close()


def insert_chunk(conn, table, rows):
    # rows: list of tuples (label, confidence, timestamp, source)
    sql = f"INSERT INTO {table} (label, confidence, timestamp, source) VALUES (%s, %s, %s, %s)"
    cur = conn.cursor()
    cur.executemany(sql, rows)
    conn.commit()
    cnt = cur.rowcount
    cur.close()
    return cnt


def process_file_to_table(conn, csv_path, table_name, chunk_size=1000):
    print(f"Processing {csv_path} -> {table_name}")
    total_inserted = 0
    # read in chunks
    for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
        # Determine label column (clothing_label or emotion or other)
        if 'clothing_label' in chunk.columns:
            label_col = 'clothing_label'
        elif 'emotion' in chunk.columns:
            label_col = 'emotion'
        elif 'label' in chunk.columns:
            label_col = 'label'
        else:
            raise KeyError(f"No label column found in {csv_path}")

        if 'timestamp' not in chunk.columns:
            raise KeyError(f"No timestamp column in {csv_path}")

        src = os.path.splitext(os.path.basename(csv_path))[0]

        rows = []
        # iterate rows and prepare tuples
        for _, r in chunk.iterrows():
            label = r.get(label_col)
            conf = r.get('confidence') if 'confidence' in r.index else None
            ts = r.get('timestamp')
            # ensure timestamp string or datetime
            if pd.isna(ts):
                ts_val = None
            else:
                ts_val = str(ts)
            rows.append((label, float(conf) if pd.notnull(conf) else None, ts_val, src))

        inserted = insert_chunk(conn, table_name, rows)
        total_inserted += inserted
        print(f"Inserted {inserted} rows into {table_name}")

    print(f"Finished {csv_path}: total inserted {total_inserted} into {table_name}")
    return total_inserted


def analyze_table(conn, table_name):
    cur = conn.cursor()
    # total rows
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    total = cur.fetchone()[0]
    # date range
    cur.execute(f"SELECT MIN(timestamp), MAX(timestamp) FROM {table_name}")
    min_ts, max_ts = cur.fetchone()
    # top labels
    cur.execute(f"SELECT label, COUNT(*) as c FROM {table_name} GROUP BY label ORDER BY c DESC LIMIT 10")
    top = cur.fetchall()
    cur.close()
    return {
        'table': table_name,
        'total': total,
        'min_timestamp': min_ts,
        'max_timestamp': max_ts,
        'top_labels': top,
    }


def main():
    # only these two files
    mappings = [
        ('data_kepala.csv', 'head_track'),
    ]

    conn = connect_db()
    try:
        create_tables(conn)

        results = []
        for csv_file, table in mappings:
            if not os.path.exists(csv_file):
                print(f"Skipping missing file: {csv_file}")
                continue
            inserted = process_file_to_table(conn, csv_file, table)
            results.append((csv_file, table, inserted))

        print('\nInjection summary:')
        for r in results:
            print(r)

        print('\nAnalyzing tables...')
        analyses = []
        for _, table in mappings:
            # check table exists
            cur = conn.cursor()
            cur.execute(f"SHOW TABLES LIKE '{table}'")
            if cur.fetchone():
                analyses.append(analyze_table(conn, table))
            cur.close()

        for a in analyses:
            print('\nTable:', a['table'])
            print(' Total rows:', a['total'])
            print(' Date range:', a['min_timestamp'], '->', a['max_timestamp'])
            print(' Top labels:')
            for label, c in a['top_labels']:
                print(f"  {label}: {c}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
