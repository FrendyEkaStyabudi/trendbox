"""
generate_shifted_data.py

Create new CSV copies of `data_baju.csv` and `data_kepala.csv` where the dates
are remapped to start from today and span the same number of distinct days as
the original file. Time-of-day is preserved; only the date component is shifted.

Outputs (per input file): `*_shifted.csv` (same columns, updated `timestamp`).

Usage:
  python generate_shifted_data.py
  python generate_shifted_data.py --start 2025-12-01  # optional start date
"""
import os
from datetime import date, timedelta
import pandas as pd
from dateutil import parser as date_parser


def parse_timestamps(col: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(col, errors='coerce')
    if parsed.isna().any():
        mask = parsed.isna()
        parsed_vals = col[mask].apply(lambda x: date_parser.parse(x) if pd.notnull(x) else pd.NaT)
        parsed.loc[mask] = parsed_vals
    return parsed


def remap_dates(df: pd.DataFrame, start_date: date) -> pd.DataFrame:
    # Ensure timestamp column exists and is parsed
    if 'timestamp' not in df.columns:
        raise KeyError("Input dataframe must have a 'timestamp' column")
    df['timestamp'] = parse_timestamps(df['timestamp'])

    # Map original distinct dates (sorted) to consecutive dates starting at start_date
    df['orig_date'] = df['timestamp'].dt.date
    unique_dates = sorted(df['orig_date'].dropna().unique())
    if not unique_dates:
        raise ValueError('No valid dates found in timestamp column')

    n_days = len(unique_dates)
    new_dates = [start_date + timedelta(days=i) for i in range(n_days)]
    mapping = dict(zip(unique_dates, new_dates))

    # Apply mapping: preserve time-of-day, change date
    def shift_ts(ts):
        if pd.isna(ts):
            return ts
        orig_d = ts.date()
        new_d = mapping.get(orig_d)
        if new_d is None:
            # if date not in mapping (shouldn't happen), keep original
            return ts
        return pd.Timestamp.combine(new_d, ts.time())

    df['timestamp'] = df['timestamp'].apply(shift_ts)
    df = df.drop(columns=['orig_date'])
    return df


def process_file(path: str, start_date: date = None):
    name = os.path.splitext(os.path.basename(path))[0]
    df = pd.read_csv(path)
    # If start_date not provided, use today
    if start_date is None:
        start_date = date.today()

    # Compute number of distinct original dates to report
    df['timestamp'] = parse_timestamps(df['timestamp'])
    orig_dates = sorted(df['timestamp'].dt.date.dropna().unique())
    n_days = len(orig_dates)

    print(f"File: {path} -> distinct days: {n_days}; remapping starting at {start_date}")

    df_shifted = remap_dates(df.copy(), start_date=start_date)

    out_name = f"{name}_shifted.csv"
    df_shifted.to_csv(out_name, index=False)
    print(f"Wrote: {out_name} ({len(df_shifted)} rows)")
    return out_name, n_days, start_date


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate shifted copies of data_baju and data_kepala')
    parser.add_argument('--start', type=str, default=None, help='Start date for remapped data (YYYY-MM-DD). Defaults to today.')
    args = parser.parse_args()

    if args.start:
        start_date = pd.to_datetime(args.start).date()
    else:
        start_date = date.today()

    inputs = ['data_baju.csv', 'data_kepala.csv']
    results = []
    for p in inputs:
        if not os.path.exists(p):
            print(f"Skipping: {p} not found")
            continue
        out, n_days, s = process_file(p, start_date=start_date)
        # advance start_date for next file so their ranges don't overlap
        start_date = start_date + timedelta(days=n_days)
        results.append((p, out, n_days))

    print('\nDone. Summary:')
    for r in results:
        print(r)


if __name__ == '__main__':
    main()
