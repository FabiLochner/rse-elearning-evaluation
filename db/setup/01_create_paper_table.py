#!/usr/bin/env python3
"""
01_create_paper_table.py

Creates the 'paper' table in the delfi_study MySQL database.

Usage:
    python db/setup/01_create_paper_table.py

Prerequisites:
    - MySQL server running
    - .env file in project root with DB_HOST, DB_PORT, DB_USER, DB_PASSWORD

Note:
    Schema documentation: db/schema/schema_paper_only_2025-12-29.sql
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import mysql.connector

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_NAME = 'delfi_study'
TABLE_NAME = 'paper'

# DDL matching db/schema/schema_paper_only_2025-12-29.sql (copied)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `paper` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier for each paper',
  `title` VARCHAR(500) NOT NULL COMMENT 'The title of the paper',
  `authors` VARCHAR(500) NOT NULL COMMENT 'Last name and first name of the author(s) of the paper',
  `year` YEAR(4) NOT NULL COMMENT 'The publication year of the paper',
  `abstract` MEDIUMTEXT NULL DEFAULT NULL COMMENT 'The abstract of the paper',
  `text` LONGTEXT NOT NULL COMMENT 'The extracted text content of the paper (not including the abstract and references)',
  `references` MEDIUMTEXT NULL DEFAULT NULL COMMENT 'The references/bibliography section of the paper',
  `start_page` INT UNSIGNED NULL DEFAULT NULL COMMENT 'The pages of the paper',
  `end_page` INT UNSIGNED NULL DEFAULT NULL,
  `subject` VARCHAR(300) NULL DEFAULT NULL COMMENT 'The topics, subjects or keywords of the paper',
  `filename` VARCHAR(200) NOT NULL COMMENT 'The original pdf filename of the paper',
  `editors` VARCHAR(200) NULL DEFAULT NULL COMMENT 'Last name and first name of the editor(s) of the DeLFI proceeding',
  `doi` VARCHAR(50) NULL DEFAULT NULL COMMENT 'The Digital Object Identifier (DOI) which has a unique alphanumeric code to identify the paper.',
  `isbn` VARCHAR(20) NULL DEFAULT NULL COMMENT 'The International Standard Book Number (ISBN) that identifies the complete book volume for the DeLFI proceeding of each year',
  `issn` CHAR(9) NULL DEFAULT NULL COMMENT 'The International Standard Serial Number (ISSN) which is an eight-digit code to uniquely identify specific periodical publications, such as scientific journals',
  `proceeding_title` VARCHAR(200) NULL DEFAULT NULL COMMENT 'The conference proceeding title of a specific year',
  `series_title` VARCHAR(100) NULL DEFAULT NULL COMMENT 'The publication series with its volume number',
  `publisher` VARCHAR(50) NULL DEFAULT NULL COMMENT 'The publisher of the paper',
  `publication_place` CHAR(4) NULL DEFAULT NULL COMMENT 'The publication place of the paper',
  `conference_date` VARCHAR(50) NULL DEFAULT NULL COMMENT 'The date of the conference',
  `conference_location` VARCHAR(50) NULL DEFAULT NULL COMMENT 'The location of the conference',
  `session_title` VARCHAR(100) NULL DEFAULT NULL COMMENT 'The conference session or track name where the paper was presented',
  `publication_type` VARCHAR(50) NULL DEFAULT NULL COMMENT 'The publication type or format the paper was published, e.g., as an abstract or a full conference paper',
  `language` VARCHAR(10) NULL DEFAULT NULL COMMENT 'The language the paper is written in',
  `peer_review_status` CHAR(4) NULL DEFAULT NULL COMMENT 'The peer review status of the paper',
  PRIMARY KEY (`id`),
  UNIQUE INDEX `doi_UNIQUE` (`doi` ASC) VISIBLE,
  UNIQUE INDEX `title_UNIQUE` (`title` ASC) VISIBLE,
  UNIQUE INDEX `unique_year_filename` (`year` ASC, `filename` ASC) VISIBLE)
ENGINE = InnoDB;
"""

def main():
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
    }

    print(f"Creating {SCHEMA_NAME}.{TABLE_NAME}...")

    # Step 1: Create schema
    with mysql.connector.connect(**config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{SCHEMA_NAME}` DEFAULT CHARACTER SET utf8")
        conn.commit()
    print(f"  Schema '{SCHEMA_NAME}' ready")

    # Step 2: Create table
    config["database"] = SCHEMA_NAME
    with mysql.connector.connect(**config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
    print(f"  Table '{TABLE_NAME}' created")

    # Step 3: Verify
    with mysql.connector.connect(**config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{SCHEMA_NAME}' AND table_name = '{TABLE_NAME}'")
            if cursor.fetchone()[0] == 1:
                print("Done.")
            else:
                print("Error: Table verification failed")
                sys.exit(1)


if __name__ == "__main__":
    main()
