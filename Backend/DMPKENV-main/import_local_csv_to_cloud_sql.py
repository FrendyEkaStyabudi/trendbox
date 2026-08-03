import argparse
import os

from google.cloud.sql.connector import Connector, IPTypes
from google.cloud import secretmanager

import rebuild_local_db as importer


DEFAULT_INSTANCE = "trendbox-2026:asia-southeast2:trendbox-mysql"
TABLES = ("emotion_track", "clothing_track", "head_track", "attribute_track")


def table_counts(conn):
    cursor = conn.cursor()
    try:
        counts = {}
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            counts[table] = int(cursor.fetchone()[0])
        return counts
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser(
        description="Import dataset CSV lokal Trendbox ke Cloud SQL for MySQL."
    )
    parser.add_argument(
        "--instance-connection-name",
        default=os.getenv("INSTANCE_CONNECTION_NAME", DEFAULT_INSTANCE),
    )
    parser.add_argument("--database", default="trendbox")
    parser.add_argument("--user", default="trendbox-app")
    parser.add_argument("--project-id", default="trendbox-2026")
    parser.add_argument("--password-secret", default="trendbox-db-password")
    parser.add_argument("--emotion-csv", default="dec2025_emotion_data_indonesia.csv")
    parser.add_argument("--clothing-csv", default="data_baju.csv")
    parser.add_argument("--head-csv", default="data_kepala.csv")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Kosongkan empat tabel sebelum impor. Gunakan hanya jika memang ingin mengganti semua data.",
    )
    args = parser.parse_args()

    secret_client = secretmanager.SecretManagerServiceClient()
    secret_name = (
        f"projects/{args.project_id}/secrets/{args.password_secret}/versions/latest"
    )
    password = secret_client.access_secret_version(
        request={"name": secret_name}
    ).payload.data.decode("utf-8")
    print(f"Password dibaca dari Secret Manager: {args.password_secret}")
    connector = Connector(ip_type=IPTypes.PUBLIC, refresh_strategy="LAZY")
    conn = None
    try:
        conn = connector.connect(
            args.instance_connection_name,
            "pymysql",
            user=args.user,
            password=password,
            db=args.database,
        )
        importer.create_tables(conn)
        counts_before = table_counts(conn)
        print("Jumlah data sebelum impor:", counts_before)

        if any(counts_before.values()) and not args.reset:
            raise RuntimeError(
                "Database tidak kosong. Jalankan kembali dengan --reset hanya jika data lama boleh dihapus."
            )

        if args.reset:
            confirmation = input("Ketik RESET untuk mengosongkan tabel sebelum impor: ")
            if confirmation != "RESET":
                raise RuntimeError("Impor dibatalkan; konfirmasi RESET tidak diberikan.")
            importer.reset_tables(conn)

        importer.import_emotions(conn, args.emotion_csv)
        importer.import_attribute_file(
            conn, args.clothing_csv, "clothing_track", keep_clothing_label=True
        )
        importer.import_attribute_file(conn, args.head_csv, "head_track")

        print("\nHasil akhir:")
        importer.show_counts(conn)
    finally:
        if conn is not None:
            conn.close()
        connector.close()


if __name__ == "__main__":
    main()
