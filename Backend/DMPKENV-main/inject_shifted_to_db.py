"""
inject_shifted_to_db.py

Reads all '*_shifted.csv' files in the project directory and inserts their rows
into the MySQL table `attribute_track` in the `railway` database using
credentials from `injectsqldataattribut.py`.

Notes:
- The CSV `id` column is ignored (the table uses AUTO_INCREMENT primary key).
- Columns inserted: `clothing_label`, `confidence`, `timestamp`, `source`.
- The script will create `attribute_track` if it does not exist.
"""
import glob
import os
import mysql.connector
import pandas as pd
from mysql.connector import errorcode

from injectsqldataattribut import DB_CONFIG


TABLE_NAME = 'attribute_track'


def create_table_if_not_exists(conn):
    create_stmt = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id INT NOT NULL AUTO_INCREMENT,
        clothing_label VARCHAR(255),
        confidence FLOAT,
        timestamp DATETIME,
        source VARCHAR(128),
        PRIMARY KEY (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cursor = conn.cursor()
    cursor.execute(create_stmt)
    cursor.close()


def insert_rows(conn, rows):
    # rows: list of tuples (clothing_label, confidence, timestamp, source)
    sql = f"INSERT INTO {TABLE_NAME} (clothing_label, confidence, timestamp, source) VALUES (%s, %s, %s, %s)"
    cursor = conn.cursor()
    cursor.executemany(sql, rows)
    conn.commit()
    inserted = cursor.rowcount
    cursor.close()
    return inserted


def process_file(conn, path, batch_size=1000):
    print(f"Processing {path} ...")
    # read in chunks to avoid high memory usage
    inserted_total = 0
    for chunk in pd.read_csv(path, chunksize=batch_size):
        # Ensure required columns exist
        # Accept either 'clothing_label' or 'emotion' column names
        if 'clothing_label' in chunk.columns:
            label_col = 'clothing_label'
        elif 'emotion' in chunk.columns:
            label_col = 'emotion'
        else:
            raise KeyError(f"No label column found in {path} (expected 'clothing_label' or 'emotion')")

        # timestamp column
        if 'timestamp' not in chunk.columns:
            raise KeyError(f"No 'timestamp' column in {path}")

        # source: if present in CSV use it, else derive from filename
        if 'source' in chunk.columns:
            source_vals = chunk['source'].astype(str).tolist()
        else:
            src = os.path.splitext(os.path.basename(path))[0]
            source_vals = [src] * len(chunk)

        rows = []
        for i, row in chunk.iterrows():
            label = row.get(label_col)
            conf = row.get('confidence') if 'confidence' in row.index else None
            ts = row.get('timestamp')
            srcv = source_vals[i - chunk.index[0]] if isinstance(source_vals, list) else src
            # MySQL connector accepts str for datetime
            rows.append((label, float(conf) if pd.notnull(conf) else None, str(ts), srcv))

        inserted = insert_rows(conn, rows)
        inserted_total += inserted
        print(f"Inserted {inserted} rows from chunk")

    print(f"Finished {path}: inserted total {inserted_total}")
    return inserted_total


def main():
    files = sorted(glob.glob('*_shifted.csv'))
    if not files:
        print("No '*_shifted.csv' files found in current directory. Nothing to insert.")
        return

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
        return

    try:
        create_table_if_not_exists(conn)
        total = 0
        for f in files:
            total += process_file(conn, f)
        print(f"All done. Total inserted rows: {total}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
