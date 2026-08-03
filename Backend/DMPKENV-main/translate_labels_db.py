"""
translate_labels_db.py

Translate label values in DB tables from Indonesian to English according to agreed mapping.
Does not rename columns or modify schema — only updates label values in-place.

Run: python translate_labels_db.py
"""
import mysql.connector
from injectsqldataattribut import DB_CONFIG


MAPPINGS = {
    'clothing_track': {
        'kaos': 't-shirt',
        'sweater': 'sweater',
        'outer': 'outer',
        'celana_panjang': 'long_pants',
        'celana_pendek': 'shorts',
        'kemeja': 'shirt',
        'blouse': 'blouse',
        'rok': 'skirt',
    },
    'head_track': {
        'rambut': 'hair',
        'topi': 'hat',
        'hijab': 'hijab',
    }
}


def connect_db():
    return mysql.connector.connect(**DB_CONFIG)


def apply_mappings(conn):
    cur = conn.cursor()
    for table, mapping in MAPPINGS.items():
        print(f"Applying mapping for table {table}...")
        for src_val, tgt_val in mapping.items():
            sql = f"UPDATE {table} SET label = %s WHERE label = %s"
            cur.execute(sql, (tgt_val, src_val))
            print(f"  {src_val} -> {tgt_val}: affected {cur.rowcount}")
        conn.commit()
    cur.close()


def analyze_tables(conn):
    cur = conn.cursor()
    for table in MAPPINGS.keys():
        print(f"\nAnalysis for {table}:")
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
        cur.execute(f"SELECT MIN(timestamp), MAX(timestamp) FROM {table}")
        min_ts, max_ts = cur.fetchone()
        print(f" Total rows: {total}")
        print(f" Date range: {min_ts} -> {max_ts}")
        cur.execute(f"SELECT label, COUNT(*) as c FROM {table} GROUP BY label ORDER BY c DESC LIMIT 20")
        rows = cur.fetchall()
        print(" Top labels:")
        for label, c in rows:
            print(f"  {label}: {c}")
    cur.close()


def main():
    conn = connect_db()
    try:
        apply_mappings(conn)
        analyze_tables(conn)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
