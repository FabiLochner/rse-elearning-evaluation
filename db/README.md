# Database Setup Guide

## Prerequisites
- MySQL 8.4+ installed
- `.env` file configured with database credentials
- Python with `mysql-connector-python` and `python-dotenv`

## Database Structure

### delfi_study
Main database containing:
- `paper` table: DeLFI paper with metadata



## Setup Instructions

### Phase 1: Create Paper Table (Current)


**Option A: Using Python Script (Recommended)**
```bash
# From project root
python3 db/setup/01_create_paper_table.py
```

**Option B: Using Terminal (Recommended)**
```bash
# From project root
mysql -u your_user -p < db/schema/schema_paper_only_2025-12-29.sql
```

**Option C: Using MySQL Workbench**

1. Open MySQL Workbench and connect to your server. [Official Documentation](https://dev.mysql.com/doc/workbench/en/wb-getting-started-tutorial-create-connection.html)
2. File → Open SQL Script → select db/schema/schema_paper_only_2025-12-29.sql
3. Click the ⚡ lightning bolt to execute
4. Refresh the SCHEMAS panel to see delfi_study.paper


### Phase 2: Insert Paper Data


### Phase 3: Create LLM Annotations Tables


### Phase 4: Insert LLM Annotations Data 


## File Structure

db/
├── schema/                  # SQL schema files (source of truth)
│   └── schema_paper_only_2025-12-29.sql
├── setup/                   # Python scripts to execute schemas
│   └── 01_create_paper_table.py
└── test/crud/               # Database connection tests
    └── mysql_crud_test.ipynb
