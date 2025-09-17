from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from output_helper import clear_output, write_output

# ====== Patterns (EN-only) ======
START = re.compile(
    r'^(?:'
    r'Date(?: of dream)?|Dream(?:\s*\d+)?|First dream|Second dream|Third dream|'
    r'The (?:second|third|fourth) dream|Dream and analysis|Dream analysis|'
    r'I (?:dreamed|dreamt|saw)\b|At night I\b|Last night I\b'
    r')\s*[:\-–]?', re.I
)
END = re.compile(r'^(?:Reviewer(?:’|\'|)s? Message|Thank you)\b', re.I)
SCENE_CONT = re.compile(r'^(?:A next scene|Next scene|In another (?:day|scene))\b', re.I)

FIELD_DATE = re.compile(r'^(?:Date(?: of dream)?|Dream Date|Date)\s*:\s*(.+)$', re.I)
FIELD_STATE = re.compile(r'^(?:State of mind|Mood|Feeling)\s*:\s*(.+)$', re.I)
FIELD_ANALYSIS = re.compile(r'^(?:Dream and analysis|Dream analysis)\s*[:\-–]?\s*$', re.I)

# ====== Data model ======
@dataclass
class DreamRow:
    case_id: str
    dream_id: str
    date: Optional[str]
    dream_text: str
    state_of_mind: Optional[str]
    notes: str

# ====== Utilities ======
def _extract_text_pymupdf(pdf_path: Path) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    text = []
    for page in doc:
        # 'text' preserves paragraphs better than 'blocks' for this task
        text.append(page.get_text("text"))
    return "\n".join(text)

def _normalize_lines(text: str) -> list[str]:
    # collapse weird spacing, keep line structure (helps markers)
    lines = []
    for raw in text.splitlines():
        line = re.sub(r'\s+', ' ', raw).strip()
        if line:  # drop empty after normalization
            lines.append(line)
    return lines

def _split_dream_chunks(lines: list[str]) -> list[str]:
    chunks, cur = [], []
    for line in lines:
        # Start a new chunk when a new START marker appears (and we have content)
        if START.match(line) and cur:
            chunks.append("\n".join(cur).strip())
            cur = [line]
        else:
            cur.append(line)
        # Hard end markers close the current chunk
        if END.match(line) and cur:
            chunks.append("\n".join(cur).strip())
            cur = []
    if cur:
        chunks.append("\n".join(cur).strip())

    # Merge scene continuations back into previous chunk
    merged: list[str] = []
    for ch in chunks:
        first = ch.splitlines()[0]
        if SCENE_CONT.match(first) and merged:
            merged[-1] = merged[-1] + "\n" + ch
        else:
            merged.append(ch)
    return merged

# Try a handful of common English formats before falling back
_DATE_FORMATS = [
    "%B %d, %Y",      # January 02, 2024
    "%b %d, %Y",      # Jan 02, 2024
    "%d %B %Y",       # 02 January 2024
    "%d %b %Y",       # 02 Jan 2024
    "%Y-%m-%d",       # 2024-01-02
    "%m/%d/%Y",       # 01/02/2024
    "%d/%m/%Y",       # 02/01/2024
]

def _parse_date_to_iso(s: str) -> Optional[str]:
    s = s.strip().rstrip(".")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    # Very loose month name with ordinal removal (e.g., "January 2nd, 2024")
    s2 = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', s, flags=re.I)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s2, fmt).date().isoformat()
        except ValueError:
            continue
    return None

def _clean_dream_text(s: str) -> str:
    # Remove leading/trailing straight or curly quotes, including triple quotes
    s = s.strip()
    s = re.sub(r'^\s*(?:"{1,3}|“{1,3}|\'{1,3})', '', s)
    s = re.sub(r'(?:"{1,3}|”{1,3}|\'{1,3})\s*$', '', s)
    # Normalize internal spacing a bit
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()

def _increment_dream_id(last_id: str) -> str:
    # last_id like "D0000" → return next
    m = re.match(r'^[Dd](\d{4})$', last_id or "D0000")
    n = int(m.group(1)) if m else 0
    return f"D{n+1:04d}"

def _parse_fields_from_chunk(chunk: str) -> tuple[Optional[str], Optional[str], str]:
    """
    Return (date_iso, state_of_mind, dream_text_without_headers)
    """
    date_iso: Optional[str] = None
    state: Optional[str] = None

    lines = chunk.splitlines()
    body_lines: list[str] = []

    for line in lines:
        md = FIELD_DATE.match(line)
        if md and not date_iso:
            date_iso = _parse_date_to_iso(md.group(1))
            continue

        ms = FIELD_STATE.match(line)
        if ms and not state:
            state = ms.group(1).strip()
            continue

        # Skip pure analysis header lines from body
        if FIELD_ANALYSIS.match(line):
            continue

        body_lines.append(line)

    body = "\n".join(body_lines).strip()

    # If the top line is a generic "Dream X" heading, drop it from body
    if body:
        top = body.splitlines()[0]
        if re.match(r'^(?:Dream(?:\s*\d+)?|First dream|Second dream|Third dream)\b', top, re.I):
            body = "\n".join(body.splitlines()[1:]).strip()

    return date_iso, state, body

# ====== Public API ======
def parse_pdf_into_dream_rows(
    pdf_path: str | Path,
    last_dream_id: str = "D0000",
    default_case_id: str = "C01",
) -> List[DreamRow]:
    """
    Input: path to a single PDF file (English content).
    Output: list of DreamRow objects with fields:
      case_id (default C01), dream_id (Dxxxx), date (ISO or None),
      dream_text, state_of_mind (or None), notes ("From PDF: <title>").
    """
    pdf_path = Path(pdf_path)
    title_pdf = pdf_path.stem

    text = _extract_text_pymupdf(pdf_path)
    lines = _normalize_lines(text)
    chunks = _split_dream_chunks(lines)

    rows: List[DreamRow] = []
    current_id = last_dream_id

    for ch in chunks:
        date_iso, state, body = _parse_fields_from_chunk(ch)

        # Separate analysis if someone inlines it in body with a colon
        # e.g., "... Dream analysis: <text>" → remove that from dream_text
        body = re.sub(r'\bDream (?:and )?analysis\s*:\s*.*$', '', body, flags=re.I).strip()

        cleaned = _clean_dream_text(body)
        if not cleaned:
            continue  # skip empty after cleaning

        current_id = _increment_dream_id(current_id)
        rows.append(
            DreamRow(
                case_id=default_case_id,
                dream_id=current_id,
                date=date_iso,
                dream_text=cleaned,
                state_of_mind=state.strip() if state else None,
                notes=f"From PDF: {title_pdf}",
            )
        )

    return rows

# ====== Convenience: parse from raw text instead of PDF ======
def parse_text_into_dream_rows(
    raw_text: str,
    title_for_notes: str = "unknown",
    last_dream_id: str = "D0000",
    default_case_id: str = "C01",
) -> List[DreamRow]:
    lines = _normalize_lines(raw_text)
    chunks = _split_dream_chunks(lines)

    rows: List[DreamRow] = []
    current_id = last_dream_id

    for ch in chunks:
        date_iso, state, body = _parse_fields_from_chunk(ch)
        body = re.sub(r'\bDream (?:and )?analysis\s*:\s*.*$', '', body, flags=re.I).strip()
        cleaned = _clean_dream_text(body)
        if not cleaned:
            continue
        current_id = _increment_dream_id(current_id)
        rows.append(
            DreamRow(
                case_id=default_case_id,
                dream_id=current_id,
                date=date_iso,
                dream_text=cleaned,
                state_of_mind=state.strip() if state else None,
                notes=f"From PDF: {title_for_notes}",
            )
        )
    return rows

BASE_DIR = Path(__file__).resolve().parent.parent
folder = BASE_DIR / "data/D"

# ====== Example ======
if __name__ == "__main__":
  clear_output("output_test.txt")
  for file in folder.rglob("*"):
    pdf = file
    rows = parse_pdf_into_dream_rows(pdf, last_dream_id="D0000")
    for r in rows:      
      write_output(str(asdict(r)) + "\n", "output_test.txt")
