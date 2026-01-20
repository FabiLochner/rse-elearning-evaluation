# Preprocessing

## Overview

This module handles PDF text extraction and preprocessing for DELFI conference papers. It provides regex-based extraction of main content and references from academic publications, along with metadata analysis to empirically guide the design of the 'paper' table in the MySQL 'delfi_study' database.

## Prerequisites

- Python 3.13 or higher
- PyMuPDF (see [project root README](../README.md) for installation)
- Jupyter Notebook (for interactive analysis)

## File Structure

```
preprocessing/
├── pdf_text_extraction.py      # Core extraction functions
├── metadata_analysis.ipynb     # Metadata inspection and normalization
└── README.md                   # This file
```

## Core Functions

### `pdf_text_extraction.py`

**Main extraction functions:**
- `extract_text_from_pdf(pdf_path)` - Raw text extraction using PyMuPDF
- `extract_main_content(raw_text)` - Extracts main content (introduction to references)
- `extract_references(raw_text)` - Extracts bibliography/references section

**Helper functions:**
- `_is_corrupted_text(text)` - Detects garbled/corrupted PDF text
- `process_pdf_with_metadata(pdf_path)` - High-level processing for papers with metadata
- `process_pdf_without_metadata(pdf_path)` - High-level processing for papers without metadata (partial implementation)

### `metadata_analysis.ipynb`

Notebook for inspecting metadata across different DELFI proceedings years to: 1) decide which of all columns to keep for the MySQL 'paper' table, 2) analyze the empirical character length distribution of string columns to determine the design of the relevant columns in the MySQL 'paper' table.

## Validation & Test Coverage

### Tested Papers ✓

The extraction functions have been validated on **809 DELFI papers**:

| Paper Length | Page Range | Count | Status |
|--------------|------------|-------|--------|
| Short Papers | 3-7 pages  | 321   | ✓ Validated |
| Long Papers  | ≥ 8 pages  | 488   | ✓ Validated |
| **Total**    | **> 2 pages** | **809** | **✓ Working** |

### Not Tested ✗

| Paper Length | Page Range | Count | Status |
|--------------|------------|-------|--------|
| Very Short Papers | 1-2 pages | 248 | ✗ Not validated |

**Reason**: The reference paper also excluded all very short papers for classification, since it is very unlikely that they include a sufficient description of the role of research software - which is the focus of this project's evaluation - due to their shortness. 

### Excluded from Testing

- Full proceedings PDF files (multi-paper compilations)


## Known Limitations

### 1. Very Short Papers (1-2 pages)

**Status**: Not validated, may not work correctly

**Potential fix**: Priority 6 pattern (currently commented out in code) may address this, but requires testing to avoid breaking existing extractions.

### 2. Multiline Keyword Sections

**Issue**: Main content extraction starts at 2nd keyword line instead of introduction header

**Impact**:
- Additional keywords included at start of extracted main content
- Actual main content is complete and correct

**Example**:
```
Keywords: machine learning, e-learning,
educational technology, assessment
```
Extraction starts at "educational technology" line instead of "1 Introduction" below it.

**Why not fixed**:
Due to high variation in paper formats (long/medium/short papers, with/without abstracts, numbered vs unnumbered sections), fixing this edge case risks breaking the 809 currently working extractions.

**Workaround**: Keywords can be filtered during post-processing if needed.


### 3. Single file with footnotes and without standard structure

**Issue** (`lni52/GI.-.Proceedings.52-2.pdf`, 4 pages):
- Missing: Standard headings, abstract, keywords
- Result: Main content extraction starts on page 2 due to footnote detection

**Impact**:
- First page of the paper is not extracted in the main content

**Why not fixed**:
Since, it's only n = 1 paper, the additional amount of time to debug would be not worth the additional benefit 

## Usage

### Basic Usage

```python
from preprocessing.pdf_text_extraction import (
    extract_text_from_pdf,
    extract_main_content,
    extract_references
)

# Extract from PDF
pdf_path = Path("../data/lni233/15.pdf")
raw_text = extract_text_from_pdf(pdf_path)

# Get main content and references
main_content = extract_main_content(raw_text)
references = extract_references(raw_text)
```

### With Metadata

```python
from preprocessing.pdf_text_extraction import process_pdf_with_metadata

result = process_pdf_with_metadata(pdf_path)
# Returns: {'text': main_content, 'references': references}
```

### Corrupted Text Detection

The functions automatically detect corrupted/garbled text:

```python
main_content = extract_main_content(raw_text)
if main_content == "Corrupted text":
    print("PDF has encoding issues")
```

## Pattern Matching Hierarchy

`extract_main_content()` uses a priority-based pattern matching system:

1. **Priority 1**: Number + Keywords (`1 Introduction`, `1. Einleitung`)
2. **Priority 2**: Keywords only (standalone `Introduction` in first 2000 chars)
3. **Priority 3**: Below Abstract (paragraph break after abstract text)
4. **Priority 4**: Below Keywords (first line after `Keywords:`)
5. **Priority 5**: Number + Any title (e.g., `1 Two Traditions`)

`extract_references()` validates reference sections by checking for actual citation patterns (DeLFI-style `[BBS01]`, numeric `[1]`, author-year formats).


## See Also

- [Database Setup Guide](../db/README.md) - Database structure and setup
- [Project README](../README.md) - Installation and dependencies

