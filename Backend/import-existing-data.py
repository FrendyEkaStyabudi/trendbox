import argparse
import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


ROOT = Path(__file__).resolve().parent
ALLOWED_TABLES = {"emotion_track", "clothing_track", "head_track", "attribute_track"}


def load_env(path):
    values = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def get_db_config():
    env = os.environ.copy()
    env.update(load_env(ROOT / ".env"))
    return {
        "host": env.get("DB_HOST", "127.0.0.1"),
        "port": int(env.get("DB_PORT", "5432")),
        "user": env.get("DB_USER", "postgres"),
        "password": env.get("DB_PASSWORD", ""),
        "dbname": env.get("DB_DATABASE", env.get("DB_NAME", "postgres")),
    }


def get_table_columns(conn, table):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        return [row[0] for row in cursor.fetchall()]


def pick_label(row, label_column):
    if label_column and label_column in row.index:
        return row[label_column]
    for candidate in ("label", "clothing_label", "emotion"):
        if candidate in row.index:
            return row[candidate]
    return None


def normalize_rows(df, table, table_columns, label_column, source):
    insert_columns = [column for column in table_columns if column != "id"]
    rows = []

    for _, row in df.iterrows():
        values = {}

        if table == "emotion_track":
            values["user_id"] = row.get("user_id")
            values["emotion"] = row.get("emotion")
            values["confidence"] = row.get("confidence")
            values["timestamp"] = row.get("timestamp")
        else:
            label = pick_label(row, label_column)
            values["label"] = label
            values["clothing_label"] = label
            values["confidence"] = row.get("confidence")
            values["timestamp"] = row.get("timestamp")
            values["source"] = row.get("source", source)

        rows.append(tuple(None if pd.isna(values.get(column)) else values.get(column) for column in insert_columns))

    return insert_columns, rows


def import_csv(args):
    if args.table not in ALLOWED_TABLES:
        raise ValueError(f"Tabel tidak diizinkan: {args.table}")

    csv_path = Path(args.file)
    if not csv_path.is_absolute():
        csv_path = ROOT / csv_path
    if not csv_path.exists():
        raise FileNotFoundError(f"File CSV tidak ditemukan: {csv_path}")

    df = pd.read_csv(csv_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.where(pd.notnull(df), None)

    db_config = get_db_config()
    with psycopg2.connect(**db_config) as conn:
        table_columns = get_table_columns(conn, args.table)
        if not table_columns:
            raise RuntimeError(f"Tabel public.{args.table} tidak ditemukan di database.")

        insert_columns, rows = normalize_rows(
            df,
            args.table,
            table_columns,
            args.label_column,
            source=args.source or csv_path.stem,
        )
        usable_columns = [column for column in insert_columns if any(row[insert_columns.index(column)] is not None for row in rows)]
        usable_indexes = [insert_columns.index(column) for column in usable_columns]
        usable_rows = [tuple(row[index] for index in usable_indexes) for row in rows]

        print(f"Database: {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}")
        print(f"CSV: {csv_path}")
        print(f"Tabel: {args.table}")
        print(f"Kolom tabel: {', '.join(table_columns)}")
        print(f"Kolom insert: {', '.join(usable_columns)}")
        print(f"Total baris CSV: {len(df)}")

        if args.dry_run:
            print("Dry run aktif. Tidak ada data yang ditulis.")
            return

        if not usable_rows:
            print("Tidak ada baris yang bisa diinsert.")
            return

        columns_sql = ", ".join(f'"{column}"' for column in usable_columns)
        sql = f'INSERT INTO "{args.table}" ({columns_sql}) VALUES %s'
        with conn.cursor() as cursor:
            execute_values(cursor, sql, usable_rows, page_size=args.batch_size)
        conn.commit()
        print(f"Sukses insert {len(usable_rows)} baris ke {args.table}.")


def main():
    parser = argparse.ArgumentParser(description="Import CSV historis Trendbox ke Supabase/PostgreSQL.")
    parser.add_argument("--table", required=True, choices=sorted(ALLOWED_TABLES))
    parser.add_argument("--file", required=True, help="Path CSV relatif ke folder Backend atau path absolut.")
    parser.add_argument("--label-column", help="Nama kolom CSV yang dipakai sebagai label untuk clothing/head/attribute.")
    parser.add_argument("--source", help="Nilai source default jika tabel punya kolom source.")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true", help="Cek mapping tanpa insert data.")
    args = parser.parse_args()
    import_csv(args)


if __name__ == "__main__":
    main()
