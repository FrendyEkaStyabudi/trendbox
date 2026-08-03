import argparse
import os
from pathlib import Path

import mysql.connector
import pandas as pd


DEFAULT_DB_NAME = "trendbox"
PROJECT_DIR = Path(__file__).resolve().parent


TABLE_DDL = {
    "emotion_track": """
        CREATE TABLE IF NOT EXISTS emotion_track (
            id INT NOT NULL AUTO_INCREMENT,
            user_id VARCHAR(255),
            emotion VARCHAR(50),
            confidence DECIMAL(8, 4),
            timestamp DATETIME,
            PRIMARY KEY (id),
            INDEX idx_emotion_timestamp (timestamp),
            INDEX idx_emotion_label (emotion)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "clothing_track": """
        CREATE TABLE IF NOT EXISTS clothing_track (
            id INT NOT NULL AUTO_INCREMENT,
            label VARCHAR(255),
            clothing_label VARCHAR(255),
            confidence FLOAT,
            timestamp DATETIME,
            source VARCHAR(128),
            PRIMARY KEY (id),
            INDEX idx_clothing_timestamp (timestamp),
            INDEX idx_clothing_label (label)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "head_track": """
        CREATE TABLE IF NOT EXISTS head_track (
            id INT NOT NULL AUTO_INCREMENT,
            label VARCHAR(255),
            confidence FLOAT,
            timestamp DATETIME,
            source VARCHAR(128),
            PRIMARY KEY (id),
            INDEX idx_head_timestamp (timestamp),
            INDEX idx_head_label (label)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "attribute_track": """
        CREATE TABLE IF NOT EXISTS attribute_track (
            id INT NOT NULL AUTO_INCREMENT,
            clothing_label VARCHAR(255),
            confidence FLOAT,
            timestamp DATETIME,
            source VARCHAR(128),
            PRIMARY KEY (id),
            INDEX idx_attribute_timestamp (timestamp),
            INDEX idx_attribute_label (clothing_label)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
}


def db_config(database=None):
    config = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "port": int(os.getenv("DB_PORT", "3306")),
        "autocommit": False,
    }
    if database:
        config["database"] = database
    return config


def connect(database=None):
    return mysql.connector.connect(**db_config(database))


def create_database(database):
    conn = connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def create_tables(conn):
    cursor = conn.cursor()
    try:
        for ddl in TABLE_DDL.values():
            cursor.execute(ddl)
        conn.commit()
    finally:
        cursor.close()


def reset_tables(conn):
    cursor = conn.cursor()
    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in TABLE_DDL:
            cursor.execute(f"TRUNCATE TABLE `{table}`")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    finally:
        cursor.close()


def normalize_timestamp(series):
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.strftime("%Y-%m-%d %H:%M:%S").where(parsed.notna(), None)


def import_emotions(conn, csv_name):
    path = PROJECT_DIR / csv_name
    if not path.exists():
        print(f"Skip missing emotion CSV: {csv_name}")
        return 0

    sql = """
        INSERT INTO emotion_track (user_id, emotion, confidence, timestamp)
        VALUES (%s, %s, %s, %s)
    """
    total = 0
    cursor = conn.cursor()
    try:
        for chunk in pd.read_csv(path, chunksize=1000):
            required = {"user_id", "emotion", "confidence", "timestamp"}
            missing = required - set(chunk.columns)
            if missing:
                raise KeyError(f"{csv_name} missing columns: {sorted(missing)}")

            chunk["timestamp"] = normalize_timestamp(chunk["timestamp"])
            rows = [
                (
                    None if pd.isna(row.user_id) else str(row.user_id),
                    None if pd.isna(row.emotion) else str(row.emotion),
                    None if pd.isna(row.confidence) else float(row.confidence),
                    row.timestamp,
                )
                for row in chunk.itertuples(index=False)
            ]
            cursor.executemany(sql, rows)
            conn.commit()
            total += cursor.rowcount
            print(f"Inserted {total} emotion rows...", end="\r")
    finally:
        cursor.close()
    print(f"Inserted {total} rows into emotion_track from {csv_name}")
    return total


def import_attribute_file(conn, csv_name, table, keep_clothing_label=False):
    path = PROJECT_DIR / csv_name
    if not path.exists():
        print(f"Skip missing attribute CSV: {csv_name}")
        return 0

    if table == "clothing_track":
        sql = """
            INSERT INTO clothing_track (label, clothing_label, confidence, timestamp, source)
            VALUES (%s, %s, %s, %s, %s)
        """
    elif table == "head_track":
        sql = """
            INSERT INTO head_track (label, confidence, timestamp, source)
            VALUES (%s, %s, %s, %s)
        """
    else:
        raise ValueError(f"Unsupported table: {table}")

    source = Path(csv_name).stem
    total = 0
    cursor = conn.cursor()
    try:
        for chunk in pd.read_csv(path, chunksize=1000):
            label_col = next(
                (candidate for candidate in ("clothing_label", "label", "emotion") if candidate in chunk.columns),
                None,
            )
            if not label_col:
                raise KeyError(f"{csv_name} has no label column")
            if "timestamp" not in chunk.columns:
                raise KeyError(f"{csv_name} missing timestamp column")

            chunk["timestamp"] = normalize_timestamp(chunk["timestamp"])
            rows = []
            for row in chunk.itertuples(index=False):
                label = getattr(row, label_col)
                confidence = getattr(row, "confidence", None)
                label_value = None if pd.isna(label) else str(label)
                confidence_value = None if pd.isna(confidence) else float(confidence)

                if table == "clothing_track":
                    clothing_label = label_value if keep_clothing_label else None
                    rows.append((label_value, clothing_label, confidence_value, row.timestamp, source))
                else:
                    rows.append((label_value, confidence_value, row.timestamp, source))

            cursor.executemany(sql, rows)
            conn.commit()
            total += cursor.rowcount
            print(f"Inserted {total} {table} rows...", end="\r")
    finally:
        cursor.close()
    print(f"Inserted {total} rows into {table} from {csv_name}")
    return total


def show_counts(conn):
    cursor = conn.cursor()
    try:
        for table in ("emotion_track", "clothing_track", "head_track", "attribute_track"):
            cursor.execute(f"SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM `{table}`")
            count, min_ts, max_ts = cursor.fetchone()
            print(f"{table}: {count} rows, {min_ts} -> {max_ts}")
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser(description="Rebuild local Trendbox MySQL database from project CSV files.")
    parser.add_argument("--database", default=os.getenv("DB_DATABASE", DEFAULT_DB_NAME))
    parser.add_argument("--reset", action="store_true", help="Truncate tables before importing data.")
    parser.add_argument("--emotion-csv", default="dec2025_emotion_data_indonesia.csv")
    parser.add_argument("--clothing-csv", default="data_baju.csv")
    parser.add_argument("--head-csv", default="data_kepala.csv")
    args = parser.parse_args()

    print(f"Creating database `{args.database}` if needed...")
    create_database(args.database)

    conn = connect(args.database)
    try:
        create_tables(conn)
        if args.reset:
            reset_tables(conn)

        import_emotions(conn, args.emotion_csv)
        import_attribute_file(conn, args.clothing_csv, "clothing_track", keep_clothing_label=True)
        import_attribute_file(conn, args.head_csv, "head_track")
        show_counts(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
