"""
Utilities for the CSV translation dictionary feature.
Provides text normalization and hashing (MD5 + SHA1) for EN text lookup.
"""

import hashlib
import re
import unicodedata
import csv
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def normalize_en(text: str) -> str:
    """
    Normalize English text for dictionary lookup.
    - Unicode normalize (NFKC)
    - Lowercase
    - Replace whitespace runs with single spaces
    - Strip leading/trailing whitespace
    - Remove non-printable / control characters
    """
    if not text:
        return ""
    # Unicode NFKC normalization
    text = unicodedata.normalize('NFKC', text)
    # Lowercase
    text = text.lower()
    # Remove non-printable / control chars (keep normal whitespace)
    text = ''.join(ch for ch in text if not unicodedata.category(ch).startswith('C') or ch in ('\n', '\r', '\t', ' '))
    # Replace any whitespace runs (including newlines) with a single space
    text = re.sub(r'\s+', ' ', text)
    # Strip
    text = text.strip()
    return text


def hash_md5(normalized: str) -> str:
    """Compute MD5 hex digest of a normalized string (UTF-8)."""
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def hash_sha1(normalized: str) -> str:
    """Compute SHA1 hex digest of a normalized string (UTF-8)."""
    return hashlib.sha1(normalized.encode('utf-8')).hexdigest()


def parse_csv_dictionary(filepath: str) -> Tuple[List[Tuple[str, str]], int, int]:
    """
    Parse a CSV file with EN/VI columns.

    Returns:
        (entries, total_rows, skipped_rows)
        entries: list of (en_text, vi_text) pairs (raw, un-normalized)
        total_rows: total data rows encountered
        skipped_rows: rows skipped due to empty en or vi
    """
    entries: List[Tuple[str, str]] = []
    total_rows = 0
    skipped_rows = 0

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        # Peek at the first line to check for headers
        sample = f.read(4096)
        f.seek(0)
        sniffer = csv.Sniffer()

        has_header = False
        en_col = 0
        vi_col = 1

        try:
            has_header = sniffer.has_header(sample)
        except csv.Error:
            pass

        if has_header:
            reader = csv.DictReader(f)
            # Find en/vi columns case-insensitively
            if reader.fieldnames:
                lower_fields = {fn.strip().lower(): fn for fn in reader.fieldnames}
                en_field = lower_fields.get('en')
                vi_field = lower_fields.get('vi')

                if en_field and vi_field:
                    for row in reader:
                        total_rows += 1
                        en_text = (row.get(en_field) or '').strip()
                        vi_text = (row.get(vi_field) or '').strip()
                        if en_text and vi_text:
                            entries.append((en_text, vi_text))
                        else:
                            skipped_rows += 1
                    return entries, total_rows, skipped_rows

            # Header exists but no en/vi columns found - fall through to positional
            f.seek(0)
            next(f)  # skip header row

        # Positional fallback: treat first 2 columns as (en, vi)
        reader_plain = csv.reader(f)
        for row in reader_plain:
            total_rows += 1
            if len(row) < 2:
                skipped_rows += 1
                continue
            en_text = row[0].strip()
            vi_text = row[1].strip()
            if en_text and vi_text:
                entries.append((en_text, vi_text))
            else:
                skipped_rows += 1

    return entries, total_rows, skipped_rows
