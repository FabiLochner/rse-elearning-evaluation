"""
02_insert_paper_data.py

Inserts the delfi paper data from a preprocessed CSV file into the delfi_study.paper
MySQL table.

Usage:
    python3 db/setup/02_insert_paper_data.py <csv_file_path>

Example:
    python3 db/setup/02_insert_paper_data.py data/preprocessed/delfi_paper_with_metadata_2026-01-27.csv

Prerequisites:
    - MySQL server running
    - .env file in project root with DB_HOST, DB_PORT, DB_USER, DB_PASSWORD
    - Paper table created (via 01_create_paper_table.py)
    - Preprocessed CSV file (from preprocessing/data_preparation.ipynb)

Note:
    Schema documentation: db/schema/schema_paper_only_2025-12-29.sql
"""

import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import errorcode

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_NAME = 'delfi_study'
TABLE_NAME = 'paper'

# Column order must match the INSERT statement
# (excludes 'id' which is AUTO_INCREMENT)
COLUMNS = [
    'title', 'authors', 'year', 'abstract', 'text', 'references',
    'start_page', 'end_page', 'subject', 'filename', 'editors',
    'doi', 'isbn', 'issn', 'proceeding_title', 'series_title',
    'publisher', 'publication_place', 'conference_date',
    'conference_location', 'session_title', 'publication_type',
    'language', 'peer_review_status',
]


# Build parameterized INSERT statement
INSERT_SQL = (
    f"INSERT INTO `{TABLE_NAME}` "
    f"({', '.join(f'`{col}`' for col in COLUMNS)}) "
    f"VALUES ({', '.join(['%s'] * len(COLUMNS))})" #%s as placeholder
)

# Columns that are NOT NULL in the MySQL schema
NOT_NULL_COLUMNS = ['title', 'authors', 'year', 'text', 'filename']


def load_and_validate_csv(csv_path: str) -> pd.DataFrame:
    """
    Load and validate a preprocessed CSV file for database insertion.

    Checks:
        1. File exists and is readable
        2. All required columns are present
        3. NOT NULL columns contain no missing values
        4. Data types are converted (year -> int, start_page/end_page -> int or None)
        5. NaN values are replaced with None for MySQL compatibility

    Args:
        csv_path: Path to the preprocessed CSV file.

    Returns:
        Validated pandas DataFrame ready for insertion.

    Raises:
        SystemExit: If validation fails.
    """
    path = Path(csv_path)
    if not path.exists():
        print(f"Error: CSV file not found: {path}")
        sys.exit(1)

    print(f"Loading CSV: {path}")
    df = pd.read_csv(path)
    print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")

    # Check that all required columns are present
    missing_cols = set(COLUMNS) - set(df.columns)
    if missing_cols:
        print(f"Error: Missing columns in CSV: {missing_cols}")
        sys.exit(1)

    # Check NOT NULL columns for missing values
    for col in NOT_NULL_COLUMNS:
        null_count = df[col].isna().sum()
        if null_count > 0:
            print(f"Error: NOT NULL column '{col}' has {null_count} missing values")
            sys.exit(1)

    # Convert data types
    df['year'] = df['year'].astype(int)
    df['start_page'] = df['start_page'].apply(
        lambda x: int(x) if pd.notna(x) else None
    )
    df['end_page'] = df['end_page'].apply(
        lambda x: int(x) if pd.notna(x) else None
    )

    # Replace NaN with None for MySQL compatibility
    # (CSV round-trip converts None back to NaN, so this is needed again)
    df = df.where(pd.notnull(df), None)

    print("  Validation passed")
    return df


BATCH_SIZE = 50


def insert_papers(df: pd.DataFrame, config: dict) -> tuple[int, int, list]:
    """
    Insert paper records into the MySQL paper table.

    Inserts rows one at a time and commits in batches. Rows that violate
    UNIQUE constraints (duplicate doi, title, or year+filename) are skipped
    and reported.

    Args:
        df: Validated DataFrame from load_and_validate_csv().
        config: MySQL connection config dict (with 'database' key set).

    Returns:
        Tuple of (inserted_count, skipped_count, skipped_details).
        skipped_details is a list of (row_index, title, error_message).
    """
    inserted = 0
    skipped = 0
    skipped_details = []

    with mysql.connector.connect(**config) as conn:
        with conn.cursor() as cursor:
            for i, row in df.iterrows():
                values = tuple(row[col] for col in COLUMNS)
                try:
                    cursor.execute(INSERT_SQL, values)
                    inserted += 1
                except mysql.connector.IntegrityError as e:
                    skipped += 1
                    skipped_details.append((i, row['title'], str(e)))

                # Commit in batches
                if (inserted + skipped) % BATCH_SIZE == 0:
                    conn.commit()
                    print(f"  Progress: {inserted + skipped}/{len(df)} "
                          f"(inserted: {inserted}, skipped: {skipped})")

            # Final commit for remaining rows
            conn.commit()

    print(f"\nInsertion complete: {inserted} inserted, {skipped} skipped "
          f"out of {len(df)} total")

    if skipped_details:
        print(f"\nSkipped rows:")
        for idx, title, err in skipped_details:
            print(f"  Row {idx}: {title[:80]} — {err}")

    return inserted, skipped, skipped_details


def verify_insertion(config: dict, expected_count: int):
    """
    Verify the insertion by checking the row count and printing sample rows.

    Args:
        config: MySQL connection config dict (with 'database' key set).
        expected_count: Number of rows expected in the table. (will use the number of successfully inserted rows returned by insert_papers())
    """
    with mysql.connector.connect(**config) as conn:
        with conn.cursor() as cursor:
            # Row count
            cursor.execute(f"SELECT COUNT(*) FROM `{TABLE_NAME}`")
            actual_count = cursor.fetchone()[0]
            print(f"\nVerification:")
            print(f"  Rows in table: {actual_count}")
            print(f"  Expected:      {expected_count}")

            if actual_count == expected_count:
                print("  Status: OK")
            else:
                print(f"  Status: MISMATCH (difference: {actual_count - expected_count})")

            # Year distribution
            cursor.execute(
                f"SELECT `year`, COUNT(*) AS cnt FROM `{TABLE_NAME}` "
                f"GROUP BY `year` ORDER BY `year`"
            )
            rows = cursor.fetchall()
            print(f"\n  Papers per year ({len(rows)} years):")
            for year, cnt in rows:
                print(f"    {year}: {cnt}")


def main():
    # Check CLI argument
    if len(sys.argv) != 2: #if user passed too few or too many arguments to the python script
        print("Usage: python3 db/setup/02_insert_paper_data.py <csv_file_path>")
        sys.exit(1) #terminates the script immediately 

    csv_path = sys.argv[1] #sys.argv is a list that contains the command-line arguments passed to the python script (0-indexed)

    # Load environment
    env_path = PROJECT_ROOT / '.env'
    if not env_path.exists():
        print(f"Error: .env not found at {env_path}")
        sys.exit(1)
    load_dotenv(env_path)

    config = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": SCHEMA_NAME,
    }

    # Step 1: Load and validate CSV
    df = load_and_validate_csv(csv_path)

    # Step 2: Insert papers
    print(f"\nInserting {len(df)} papers into {SCHEMA_NAME}.{TABLE_NAME}...")
    inserted, skipped, _ = insert_papers(df, config)

    # Step 3: Verify
    verify_insertion(config, expected_count=inserted)

    print("\nDone.")


if __name__ == "__main__":
    main()

