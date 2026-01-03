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


def extract_main_content(raw_text: str) -> str:
    """
    Extract main text content (between intro section and references).

    Pattern Hierarchy:
        1. Number + Keywords: "1 Introduction", "1\\nEinleitung", etc.
        2. Keywords only: "Introduction" or "Einleitung" standalone (fallback)
        3. Number + Any title: "1   Two Traditions" (up to ~80 chars)
        4. Below Abstract (placeholder)
        5. Below Keywords: line after "Keywords:" for papers without numbered sections

    Args:
        raw_text: Full text extracted from PDF

    Returns:
        Main content text between start and references section
    """
    start_pos = None

    # === STEP 1: Find where main content STARTS ===

    # Priority 1: Number + Keywords combination (Introduction/Einleitung)
    # Check these FIRST to capture the section number when present
    patterns_priority_1 = [
        r'^1\s*\n\s*Introduction',      # "1\nIntroduction"
        r'^1\s*\n\s*Einleitung',        # "1\nEinleitung"
        r'^1\.?\s+Introduction',         # "1 Introduction" or "1. Introduction"
        r'^1\.?\s+Einleitung',           # "1 Einleitung" or "1. Einleitung"
        r'^1:\s*Introduction',           # "1: Introduction"
        r'^1:\s*Einleitung',             # "1: Einleitung"
    ]

    for pattern in patterns_priority_1:
        match = re.search(pattern, raw_text, re.MULTILINE | re.IGNORECASE)
        if match:
            start_pos = match.start()
            break

    # Priority 2: Keywords only (standalone line) - fallback when no number present
    if start_pos is None:
        patterns_priority_2 = [
            r'^Introduction\s*$',
            r'^Einleitung\s*$',
            r'^Introduction:\s*.+$',  # "Introduction: subtitle"
            r'^Einleitung:\s*.+$',    # "Einleitung: subtitle"
        ]

        for pattern in patterns_priority_2:
            match = re.search(pattern, raw_text, re.MULTILINE | re.IGNORECASE)
            if match:
                start_pos = match.start()
                break

    # Priority 3: Number + Any section title (for titles like "Two Traditions")
    # Matches "1   Title Text" or "1\nTitle Text" where title is up to ~80 chars
    if start_pos is None:
        patterns_priority_3 = [
            r'^1\.?\s+[A-Za-zÄÖÜäöü][^\n]{0,80}$',  # e.g., "1   Two Traditions" (same line), but also sections starting with lowercase
            r'^1\s*\n\s*[A-Za-zÄÖÜäöü][^\n]{0,80}$',    # e.g., "1\nTwo Traditions" (separate line) but also sections starting with lowercase
        ]

        for pattern in patterns_priority_3:
            match = re.search(pattern, raw_text, re.MULTILINE)
            if match:
                start_pos = match.start()
                break

    # Priority 4: Below Abstract (placeholder - not implemented yet)
    # if start_pos is None:
    #     pass

    # Priority 5: Below Keywords - for papers where first section has no number
    if start_pos is None:
        # Find "Keywords:" line (English or German variants)
        pattern_keywords = r'^(?:Keywords|Schlüsselwörter|Schlagwörter):\s*.+$'
        match = re.search(pattern_keywords, raw_text, re.MULTILINE | re.IGNORECASE)
        if match:
            # Find the next non-empty line after Keywords (starts with uppercase)
            remaining_text = raw_text[match.end():]
            next_line_match = re.search(r'^\s*[A-ZÄÖÜ][^\n]+$', remaining_text, re.MULTILINE)
            if next_line_match:
                start_pos = match.end() + next_line_match.start()

    # Fallback: start from beginning if no pattern found
    if start_pos is None:
        start_pos = 0

    # === STEP 2: Find where main content ENDS (references section) ===
    pattern_refs = r'(?:^\d+\s*\n)?^\s*(References|Literaturverzeichnis|Literatur|Bibliography)\d*\s*$' #relevant terms with possible whitespaces and footnote
    match = re.search(pattern_refs, raw_text, re.MULTILINE | re.IGNORECASE)
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
    # Find references section - match the heading line
    pattern_refs_start = r'^\s*(References|Literaturverzeichnis|Literatur|Bibliography)\d*\s*$' #relevant terms with possible whitespaces and footnote
    match = re.search(pattern_refs_start, raw_text, re.MULTILINE | re.IGNORECASE)

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