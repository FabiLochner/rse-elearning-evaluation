"""
pdf_extraction.py

Regex functions for extracting main content and references
from DELFI PDF publications using PyMuPDF.

Usage:
    from preprocessing.pdf_extraction import (
        extract_text_from_pdf,
        extract_main_content,
        extract_references
    )
"""

import pymupdf
import re
from pathlib import Path
from typing import Optional


def extract_text_from_pdf(pdf_path: Path | str) -> str:
    """
    Extract raw text from PDF using PyMuPDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Raw text content from all pages concatenated
    """
    doc = pymupdf.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def _is_corrupted_text(text: str, sample_size: int = 2000) -> bool:
    """
    Detect if extracted PDF text is corrupted/garbled.

    Internal helper function that checks text quality using heuristics:
    - Alphabetic character ratio (should be > 30% for German/English text)
    - Control character ratio (should be < 20%, excluding newlines/tabs)

    Args:
        text: Raw text extracted from PDF
        sample_size: Number of characters to sample for analysis (default: 2000)

    Returns:
        True if text appears corrupted, False otherwise

    Examples of corrupted text:
        - "\\x1aE2F1C $ \\x05.3 \\x17.0.-\\x1c\\x1a"
        - ".">C"? \\x01FC4>"3I">0L"F*"
    """
    if len(text) == 0:
        return True

    # Sample from beginning (most indicative)
    sample = text[:min(sample_size, len(text))]

    # Count character categories
    total_chars = len(sample)
    alphabetic = sum(1 for c in sample if c.isalpha())
    control_chars = sum(1 for c in sample if ord(c) < 32 and c not in '\n\r\t')

    # Calculate proportions
    alpha_ratio = alphabetic / total_chars
    control_ratio = control_chars / total_chars

    # Thresholds based on expected German/English text (40-60% alphabetic)
    if alpha_ratio < 0.30:  # Less than 30% alphabetic
        return True
    if control_ratio > 0.20:  # More than 20% control characters
        return True

    return False


def extract_main_content(raw_text: str) -> Optional[str]:
    """
    Extract main text content (between intro section and references).

    Pattern Hierarchy:
        1. Number + Keywords: "1 Introduction", "1\\nEinleitung", etc.
        2. Keywords only: "Introduction" or "Einleitung" standalone (fallback)
        3. Below Abstract: paragraph after "Abstract:" when no Keywords exist
        4. Below Keywords: line after "Keywords:" for papers without numbered sections
        5. Number + Any title: "1   Two Traditions" (up to ~80 chars)
        6. After author/affiliation: for short papers without standard sections

    Args:
        raw_text: Full text extracted from PDF

    Returns:
        Main content text between start and references section, or None if no structure detected
    """
    # Check for corrupted text FIRST (before any pattern matching)
    if _is_corrupted_text(raw_text):
        print("WARNING: Corrupted PDF text detected (garbled encoding, missing CMap, or font issues).")
        print("         Extraction not possible. Returning None.")
        return "Corrupted text" #for debugging (later: return None)

    start_pos = None

    # === STEP 1: Find where main content STARTS ===

    # Priority 1: Number + relevant Keywords combination (e.g.,Introduction/Einleitung)
    # Check these FIRST to capture the section number when present
    patterns_priority_1 = [
        r'^\s*1\s*\n\s*(?:Introduction|Einleitung|Einführung|Background|Motivation|Hintergrund)',      # e.g., " 1\nIntroduction" or "1\nIntroduction"
        r'^\s*1\.?\s+(?:Introduction|Einleitung|Einführung|Background|Motivation|Hintergrund)',         # e.g., " 1 Introduction" or "1. Introduction"
        r'^\s*1:\s*(?:Introduction|Einleitung|Einführung|Background|Motivation|Hintergrund)',           # e.g., " 1: Introduction" or "1: Introduction"
    ]

    for pattern in patterns_priority_1:
        match = re.search(pattern, raw_text, re.MULTILINE | re.IGNORECASE)
        if match:
            start_pos = match.start()
            break

    # Priority 2: Keywords only (standalone line) - fallback when no number present
    if start_pos is None:
        # Position constraint to avoid matching keywords in body text
        # (e.g., "Einführung der Lernplattform" in middle of document)
        # Strategy: Search in a limited region near the document start

        # Check if Abstract exists to define search region
        pattern_abstract_check = r'^(?:Abstract|Zusammenfassung|Kurzfassung|Summary|Résumé):\s*'
        abstract_check = re.search(pattern_abstract_check, raw_text, re.MULTILINE | re.IGNORECASE)

        if abstract_check:
            # If Abstract exists, search only in first 2000 chars after Abstract
            # (covers typical abstract + introduction header for both short and long papers)
            search_start = abstract_check.start()
            search_end = min(len(raw_text), abstract_check.start() + 2000)
            search_region = raw_text[search_start:search_end]
            offset = search_start
        else:
            # If no Abstract, also search in first 2000 chars of document
            search_region = raw_text[:2000]
            offset = 0

        patterns_priority_2 = [
            r'^\s*(?:Introduction|Einleitung|Einführung)\s*$',  # Allow leading/trailing whitespace
            r'^\s*(?:Introduction|Einleitung|Einführung):\s*.+$',  # e.g., "Introduction: subtitle"
            r'^\s*(?:Introduction|Einleitung|Einführung)[\s–—-]+.{1,50}$',  # e.g., "Einleitung – Die chinesisch-deutsche..." (handles em-dash, en-dash, hyphen); Added a length limit to match intro headers but no text in the main body
        ]

        for pattern in patterns_priority_2:
            match = re.search(pattern, search_region, re.MULTILINE | re.IGNORECASE)
            if match:
                start_pos = offset + match.start()
                break

    # Priority 3: Below Abstract - for papers with abstract but no Keywords/Introduction
    # Strategy 1: Blank-line detection (paragraph break after Abstract)
    # Strategy 2: Period-newline-capital detection with minimum distance safeguard
    if start_pos is None:
        has_keywords = re.search(r'^(?:Keywords|Key\s+words|Schlüsselwörter|Schlagwörter|Keyphrases|Key\s+phrases|Index\s+Terms|Suchbegriffe|Stichwörter|Indexbegriffe):\s*', raw_text, re.MULTILINE | re.IGNORECASE) #look whether there are keywords below the abstract
        if not has_keywords: # Only execute if paper lacks keywords (if it has keywords go to priority 4)

            # Match "Abstract:" or German equivalent "Zusammenfassung:"
            pattern_abstract = r'^(?:Abstract|Zusammenfassung|Kurzfassung|Summary|Résumé):\s*'
            match = re.search(pattern_abstract, raw_text, re.MULTILINE | re.IGNORECASE)
            if match:
                remaining = raw_text[match.end():]

                # Strategy 1: Look for numbered section first (e.g., "1 Title" or "1\nTitle") -> same regex patterns used as in Priority 5 below
                patterns_numbered = [
                    r'^\s*1\.?\s+[A-Za-zÄÖÜäöü][^\n]{0,80}$',  # "1   Title" or "1. Title"
                    r'^\s*1\s*\n\s*[A-Za-zÄÖÜäöü][^\n]{0,80}$',  # "1\nTitle"
                ]
                for pattern in patterns_numbered:
                    match_num = re.search(pattern, remaining, re.MULTILINE)
                    if match_num:
                        start_pos = match.end() + match_num.start()
                        break

                # Strategy 2: Look for blank line followed by capital letter (only if Strategy 1 fails)
                if start_pos is None:
                    next_para = re.search(
                                r'\n\s*\n+\s*(?!Keywords|Key\s+words|Schlüsselwörter|Schlagwörter|Keyphrases|Key\s+phrases|Index\s+Terms|Suchbegriffe|Stichwörter|Indexbegriffe)([A-ZÄÖÜ])', # negative lookahead to skip Keywords variants in the blank-line detection pattern
                                remaining,
                                re.IGNORECASE
                            )
                    if next_para:
                        start_pos = match.end() + next_para.start(1)

                # Strategy 3: Period + newline + capital, with minimum distance safeguard (if Strategy 1 and 2 fail)
                # Abstracts are typically 75-300 words (~400-1800 chars)
                # We use a minimum threshold to avoid catching sentence breaks within the abstract
                if start_pos is None:
                    MIN_ABSTRACT_CHARS = 400  # ~75 words minimum abstract length

                    # Step 2a: Look for pattern AFTER minimum threshold (handles medium/long abstracts)
                    if len(remaining) > MIN_ABSTRACT_CHARS:
                        search_region = remaining[MIN_ABSTRACT_CHARS:]
                        para_break = re.search(r'\.\n([A-ZÄÖÜ])', search_region)
                        if para_break:
                            start_pos = match.end() + MIN_ABSTRACT_CHARS + para_break.start(1)

                    # Step 2b: Fallback for very short abstracts (< 75 words)
                    if start_pos is None:
                        para_break = re.search(r'\.\n([A-ZÄÖÜ])', remaining)
                        if para_break:
                            start_pos = match.end() + para_break.start(1)

    # Priority 4: Below Keywords - for papers where first section has no number
    if start_pos is None:
        # Find "Keywords:" line (English or German variants)
        pattern_keywords = r'^(?:Keywords|Key\s+words|Schlüsselwörter|Schlagwörter|Keyphrases|Key\s+phrases|Index\s+Terms|Suchbegriffe|Stichwörter|Indexbegriffe):\s*.+$'
        match = re.search(pattern_keywords, raw_text, re.MULTILINE | re.IGNORECASE)
        if match:
            remaining_text = raw_text[match.end():]
             # Strategy 1: Look for numbered section first (e.g., "1 Title" or "1\nTitle") -> same regex patterns used as in Priority 5 below
            patterns_numbered = [
                r'^\s*1\.?\s+[A-Za-zÄÖÜäöü][^\n]{0,80}$',  # "1   Title" or "1. Title"
                r'^\s*1\s*\n\s*[A-Za-zÄÖÜäöü][^\n]{0,80}$',  # "1\nTitle"
            ]
            for pattern in patterns_numbered:
                match_num = re.search(pattern, remaining_text, re.MULTILINE)
                if match_num:
                    start_pos = match.end() + match_num.start()
                    break
            # Strategy 2: Find the next non-empty line after Keywords (starts with uppercase)
            if start_pos is None: #only runs if Strategy 1 was not successful
                next_line_match = re.search(r'^\s*[A-ZÄÖÜ][^\n]+$', remaining_text, re.MULTILINE)
                if next_line_match:
                    start_pos = match.end() + next_line_match.start()

    # Priority 5: Number + Any section title (for titles like "Two Traditions")
    # Matches " 1   Title Text" or " 1\nTitle Text" where title is up to ~80 chars
    if start_pos is None:
        patterns_priority_5 = [
            r'^\s*1\.?\s+[A-Za-zÄÖÜäöü][^\n]{0,80}$',  # e.g., " 1   Two Traditions" or "1. Title" (same line)
            r'^\s*1\s*\n\s*[A-Za-zÄÖÜäöü][^\n]{0,80}$',    # e.g., " 1\nTwo Traditions" (separate line)
        ]

        for pattern in patterns_priority_5:
            match = re.search(pattern, raw_text, re.MULTILINE)
            if match:
                start_pos = match.start()
                break

    # # Priority 6: After author/affiliation - for short papers without sections
    # # Only executes if all other patterns (1-5) have failed
    # if start_pos is None:
    #     # Keywords that indicate institutional affiliations (German focus)
    #     institution_keywords = [
    #         'universität', 'hochschule', 'institut', 'fakultät',
    #         'university', 'institute', 'faculty', 'department',
    #         'fachbereich', 'arbeitsbereich', 'lehrstuhl'
    #     ]

    #     # Split text into lines for analysis
    #     lines = raw_text.split('\n')

    #     # Track position in raw text
    #     char_position = 0

    #     # Only search in first 25% of document (avoid catching mid-body text)
    #     search_limit = len(raw_text) // 4

    #     for i, line in enumerate(lines):
    #         line_stripped = line.strip()

    #         # Skip empty lines
    #         if not line_stripped:
    #             char_position += len(line) + 1  # +1 for newline
    #             continue

    #         # Check if we've exceeded search limit (past first 25% of document)
    #         if char_position > search_limit:
    #             break

    #         # Skip lines with email addresses (author contact info)
    #         if '@' in line_stripped:
    #             char_position += len(line) + 1
    #             continue

    #         # Skip lines with institutional keywords (affiliations)
    #         if any(keyword in line_stripped.lower() for keyword in institution_keywords):
    #             char_position += len(line) + 1
    #             continue

    #         # Skip very short lines (likely titles, names, or section numbers)
    #         if len(line_stripped) < 40:
    #             char_position += len(line) + 1
    #             continue

    #         # Check if line looks like a substantial paragraph
    #         # Criterion 1: Line is long enough (> 100 chars)
    #         is_long_enough = len(line_stripped) > 100

    #         # Criterion 2: Line contains multiple sentences (period + space + capital)
    #         # Pattern: ". A" or ". D" etc. (sentence boundary within line)
    #         has_multiple_sentences = bool(re.search(r'\.\s+[A-ZÄÖÜ]', line_stripped))

    #         # Criterion 3: Line starts with capital letter (German/English)
    #         starts_with_capital = line_stripped[0].isupper()

    #         # If line meets criteria for "substantial paragraph"
    #         if starts_with_capital and (is_long_enough or has_multiple_sentences):
    #             # Additional validation: check if next line continues (not isolated line)
    #             if i + 1 < len(lines):
    #                 next_line = lines[i + 1].strip()
    #                 # If next line is also substantial (not empty, not very short)
    #                 if len(next_line) > 30:
    #                     # Found start of main content
    #                     start_pos = char_position
    #                     break
    #             else:
    #                 # Last line case: accept if it's very long
    #                 if len(line_stripped) > 150:
    #                     start_pos = char_position
    #                     break

    #         char_position += len(line) + 1

    #     # Conservative approach: if uncertain, leave start_pos = None
    #     # (will return None below instead of guessing)

    # Fallback: start from beginning if no pattern found
    if start_pos is None:
        start_pos = 0

    # === STEP 2: Find where main content ENDS (references section) ===
    # Matches: optional section number (separate/same line) + keyword + optional footnote
    # Examples: "Literatur", "5\nLiteratur", "5  Literatur", "5. Literatur", "Literatur1", "Bibliografie"
    pattern_refs = r'^\s*(?:\d+\s*\n\s*|\d+\.?\s+)?(References|Literaturverzeichnis|Literatur|Bibliography|Bibliografie|Referenzen|Quellenverzeichnis|Quellen|Reference\s+List)\d*\s*$'
    #match = re.search(pattern_refs, raw_text, re.MULTILINE | re.IGNORECASE)

    # Position constraint: references must be in last 50% of document to avoid false positives
    # (e.g., "aus Vorlesungen und Literatur in der Regel" in body text)
    text_length = len(raw_text)
    min_position = int(text_length * 0.50)

    # Find ALL candidate reference headings in last 50% of document
    candidates = [
        m for m in re.finditer(pattern_refs, raw_text, re.MULTILINE | re.IGNORECASE)
        if m.start() >= min_position
    ]

    # Reference entry validation: Support multiple citation styles
    # Style 1: DeLFI-style [BBS01], [HKN01], [Ka93]
    # Style 2: Numeric [1], [2], [123]
    # Style 3: Author-year without brackets: Bruner, J.S. (1961)
    REFERENCE_PATTERNS = [
        r'\s*\[(?:[A-Za-z]{2,4}|[A-Z][a-z]{1,2})\d{2}\]',  # DeLFI-style
        r'^\s*\[\d{1,3}\]',  # Numeric style
        r'^[A-ZÄÖÜ][a-zäöüß]+,\s+[A-Z].*?\(\d{4}\)',  # Author-year style
    ]

    match = None

    # Prefer the LAST valid references section
    for m in reversed(candidates):
        # Look shortly AFTER the heading
        sample = raw_text[m.end(): min(len(raw_text), m.end() + 1500)]

        # Validate that real references follow (check all patterns)
        is_valid = any(re.search(pattern, sample, re.MULTILINE) for pattern in REFERENCE_PATTERNS)
        if is_valid:
            match = m
            break

    # # Find first match in last 50% of document
    # match = None
    # for m in re.finditer(pattern_refs, raw_text, re.MULTILINE | re.IGNORECASE):
    #     if m.start() >= min_position:
    #         match = m
    #         break

    if match:
        end_pos = match.start()
    else:
        end_pos = len(raw_text)

    # Return content without additional cleaning
    return raw_text[start_pos:end_pos]


def extract_references(raw_text: str) -> Optional[str]:
    """
    Extract the references/bibliography section from PDF text.

    Returns only the reference entries (excludes heading and trailing page info).

    Removes trailing line which can be:
        - Pattern A: Just page number ("449", "22")
        - Pattern B: Page number + authors ("208 Alexander Aumann et al.")
        - Pattern C: Title + page number ("The interplay... 21")

    Args:
        raw_text: Full text extracted from PDF

    Returns:
        References section text (without heading), or None if not found
    """
    # Check for corrupted text FIRST (before any pattern matching)
    if _is_corrupted_text(raw_text):
        return None

    # Find references section - match the heading line
    # Matches: optional section number (separate/same line) + keyword + optional footnote
    # Examples: "Literatur", "5\nLiteratur", "5  Literatur", "5. Literatur", "Literatur1", "Bibliografie"
    pattern_refs_start = r'^\s*(?:\d+\s*\n\s*|\d+\.?\s+)?(References|Literaturverzeichnis|Literatur|Bibliography|Bibliografie|Referenzen|Quellenverzeichnis|Quellen|Reference\s+List)\d*\s*$'
    #match = re.search(pattern_refs_start, raw_text, re.MULTILINE | re.IGNORECASE)

    # Position constraint: references must be in last 50% of document to avoid false positives
    # (e.g., "aus Vorlesungen und Literatur in der Regel" in body text)
    text_length = len(raw_text)
    min_position = int(text_length * 0.50)  # Must be in last 50%

    # Find all candidate reference headings in last 50%
    candidates = [
        m for m in re.finditer(pattern_refs_start, raw_text, re.MULTILINE | re.IGNORECASE)
        if m.start() >= min_position
    ]

    # Reference entry validation: Support multiple citation styles
    # Style 1: DeLFI-style [BBS01], [HKN01], [Ka93]
    # Style 2: Numeric [1], [2], [123]
    # Style 3: Author-year without brackets: Bruner, J.S. (1961)
    REFERENCE_PATTERNS = [
        r'\s*\[(?:[A-Za-z]{2,4}|[A-Z][a-z]{1,2})\d{2}\]',  # DeLFI-style
        r'^\s*\[\d{1,3}\]',  # Numeric style
        r'^[A-ZÄÖÜ][a-zäöüß]+,\s+[A-Z].*?\(\d{4}\)',  # Author-year style
    ]

    match = None
    for m in reversed(candidates):
        sample = raw_text[m.end(): min(len(raw_text), m.end() + 1500)]
        # Validate that real references follow (check all patterns)
        is_valid = any(re.search(pattern, sample, re.MULTILINE) for pattern in REFERENCE_PATTERNS)
        if is_valid:
            match = m
            break

    # # Find first match in last 50% of document
    # match = None
    # for m in re.finditer(pattern_refs_start, raw_text, re.MULTILINE | re.IGNORECASE):
    #     if m.start() >= min_position:
    #         match = m
    #         break


    if not match:
        return None

    # Start AFTER the heading (use match.end() to exclude "References" word)
    references = raw_text[match.end():].strip()

    # === Remove trailing line (separate patterns for debugging) ===

    # Pattern A: Just page number (e.g., "449", "22")
    pattern_a = r'\n\d{1,4}\s*$'
    match_a = re.search(pattern_a, references)
    if match_a:
        references = references[:match_a.start()]
        return references.strip()

    # Pattern B: Page number + authors (e.g., "208 Alexander Aumann et al.")
    pattern_b = r'\n\d{1,4}\s+[A-ZÄÖÜ][a-zäöüß]+.*$'
    match_b = re.search(pattern_b, references)
    if match_b:
        references = references[:match_b.start()]
        return references.strip()

    # Pattern C: Title + page number (e.g., "The interplay... 21")
    pattern_c = r'\n[A-ZÄÖÜ].+\s+\d{1,4}\s*$'
    match_c = re.search(pattern_c, references)
    if match_c:
        references = references[:match_c.start()]
        return references.strip()

    return references.strip()



# --- For papers WITHOUT metadata ---
def extract_title_from_pdf(raw_text: str) -> str:
    """Extract title from PDF text (for papers without metadata)."""
    ...

def extract_authors_from_pdf(raw_text: str) -> str:
    """Extract authors from PDF text (for papers without metadata)."""
    ...

def extract_abstract_from_pdf(raw_text: str) -> str | None:
    """Extract abstract from PDF text."""
    ...

# --- High-level convenience functions ---
def process_pdf_with_metadata(pdf_path: Path) -> dict:
    """Process PDF that has accompanying metadata file.
    Returns only: text, references (metadata provides the rest)."""
    raw = extract_text_from_pdf(pdf_path)
    return {
        'text': extract_main_content(raw),
        'references': extract_references(raw),
    }

def process_pdf_without_metadata(pdf_path: Path) -> dict:
    """Process PDF that lacks metadata file.
    Returns: title, authors, year, abstract, text, references."""
    raw = extract_text_from_pdf(pdf_path)
    return {
        'title': extract_title_from_pdf(raw),
        'authors': extract_authors_from_pdf(raw),
        'abstract': extract_abstract_from_pdf(raw),
        'text': extract_main_content(raw),
        'references': extract_references(raw),
        # year must be inferred from folder name
    }