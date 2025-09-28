from collections import Counter
from pathlib import Path
import re

from typing import Iterable, List, Dict, Optional

from annotated_types import doc
import fitz  # PyMuPDF

from output_helper import write_output  # PyMuPDF

from my_type import CHOOSEN_MODEL, INPUT_PATH, Dream
from ai_helper import gemini_prompt, groq_prompt

def readPdf(sub_folder, file_name, output_file_name, last_case_id="D0000") -> List[Dream]:
    id, file_path, date_from_filename, title_guess, dream_text, error = (None, None, None, None, None, None)
    file_path: Path = INPUT_PATH / sub_folder / file_name
    doc = fitz.open(file_path)
    id, date_from_filename, title_pdf = parse_filename(file_name)
    text = ""
    
    for i, page in enumerate(doc): text += page.get_text()
        
    text = extract_clean_block(text)    

    text = f"title_pdf: {title_pdf}. last case id: {last_case_id}. PDF text: {text}"

    text = clean_dream_text(text)

    write_output(text, output_file_name)
    
    return llm_filter_dream_text(text, output_file_name, title_pdf)

def llm_filter_dream_text(dream_text: str, OUTPUT_FILENAME: str, title_pdf: str) -> str:    
    
    data = gemini_prompt(dream_text, OUTPUT_FILENAME, CHOOSEN_MODEL)
    # data = groq_prompt(dream_text, OUTPUT_FILENAME, CHOOSEN_MODEL, title_pdf)
        
    data = update_dreams(data)

    return data


def parse_filename(file_name: str):

    # Bỏ đuôi .pdf (nếu có)
    base = file_name[:-4] if file_name.lower().endswith(".pdf") else file_name

    # Tìm năm 4 chữ số ở cuối
    m_year = re.search(r"(\d{4})\s*$", base)
    if not m_year:
        # Không có năm => cố gắng vẫn trả về title
        return [], None, re.sub(r"[_\s]+", " ", base).strip(" ._-")

    year = int(m_year.group(1))
    left = base[:m_year.start()]  # phần còn lại bên trái năm

    # Bắt chuỗi các ID ở đầu (1–3 chữ số), cho phép ngăn cách bằng ., ), -, hoặc khoảng trắng
    m_ids = re.match(r"^\s*((?:\d{1,3}[\s.\-)]*)+)", left)
    ids: List[int] = []
    rest = left

    if m_ids:
        # Lấy tất cả số trong block ID đầu chuỗi
        ids = [int(x) for x in re.findall(r"\d{1,3}", m_ids.group(1))]
        rest = left[m_ids.end():]  # phần sau cụm ID

    # Sau cụm ID thường là mã (D, DL, A, ...), rồi tới title
    # VD: "DL_Working with a right discernment _ " -> code="DL", title thô phía sau
    m_code_title = re.match(
        r"""^\s*                # bỏ khoảng trắng
            (?:(?P<code>[A-Za-z]+)   # mã chữ (tùy chọn)
            [._\s]+)?                 # theo sau là . hoặc _ hoặc space
            (?P<title>.*)             # phần tiêu đề còn lại
        $""",
        rest,
        flags=re.VERBOSE
    )

    if m_code_title:
        title_guess = m_code_title.group("title")
    else:
        # fallback: coi toàn bộ 'rest' là tiêu đề
        title_guess = rest

    # Chuẩn hoá title: đổi _ -> space, gộp khoảng trắng, bỏ ký tự thừa đầu/cuối
    title_guess = re.sub(r"[_\s]+", " ", title_guess).strip(" ._-")

    return ids, year, title_guess

def extract_clean_block(text: str, remove_noise=True):
    """
    Trả về đoạn từ 'Date of dream|Dream date' đến trước 'Revision|student note|Student mark'.
    Nếu remove_noise=True, sẽ cắt bỏ khúc nhiễu ( (https... ) -> ... -> dòng '1/2' ).
    """
    if not text:
        return None
    
    # Regex marker (không phân biệt hoa thường, theo dòng)
    RX_START = re.compile(r'(?im)^\s*(?:Date of dream|Dream date)\s*:?.*$')
    RX_STOP  = re.compile(r'(?im)^\s*(?:Revision|student note|Student mark)\b.*$')

    # 1) Xác định điểm bắt đầu
    m_start = RX_START.search(text)
    if not m_start:
        return None
    start_idx = m_start.start()

    # 2) Xác định điểm dừng
    m_stop = RX_STOP.search(text, start_idx)
    end_idx = m_stop.start() if m_stop else len(text)

    block = text[start_idx:end_idx]

    # 3) (Tuỳ chọn) cắt bỏ khúc nhiễu từ dòng "(https..." đến dòng "x/y"
    if remove_noise:
        block = remove_noise_chunk(block)

    # Chuẩn hoá khoảng trắng ngoài rìa
    return block

def remove_noise_chunk(block: str) -> str:
    """
    Cắt bỏ đoạn từ dòng bắt đầu bằng '(https' (trong ngoặc) cho đến dòng chỉ chứa 'x/y'.
    Nếu không có cặp đó, giữ nguyên.
    """
    RX_PAGE  = re.compile(r'(?m)^\s*\d+\s*/\s*\d+\s*$')            # ví dụ "1/2" một mình trên dòng
    RX_PAREN_HTTP_LINE = re.compile(r'(?im)^\s*\(https?://', re.IGNORECASE)
    # Tìm dòng mở đầu khúc nhiễu: một dòng bắt đầu bằng '('https...
    m_open = RX_PAREN_HTTP_LINE.search(block)
    if not m_open:
        return block

    # Tìm dòng số trang (x/y) xuất hiện SAU đó
    m_page = RX_PAGE.search(block, m_open.end())
    if not m_page:
        return block

    # Cắt bỏ đoạn [m_open.start(), m_page.end())
    cleaned = block[:m_open.start()] + block[m_page.end():]
    return cleaned

def parse_pdf_text_to_dreams(
    pdf_text: str,
    title_pdf: Optional[str] = None,
    case_id: str = "C01",
) -> List[Dict[str, str]]:
    """
    Parse the extracted text of ONE PDF and return a list of dreams with columns:
    case_id, dream_id, date, dream_text, state_of_mind, notes.

    Heuristics:
      - 'Date of dream:' and 'State of mind:' can be on the same line (Label: value)
        or the value may appear on the next non-empty line.
      - Dream content comes from the 'Dream and analysis' section (case-insensitive
        variants accepted). If absent, the whole text is used as fallback.
      - Sub-dream segmentation (in priority order):
          1) Lines like: "First/Second/Third ... dream"
          2) Lines like: "Dream 1", "Dream #2", "Dream: ..."
          3) Fallback for numbered lists inside the dream section: "1. ...", "2) ..."
             (used only if there are at least two such items)
      - If a segment contains a heading like "Analysis", "Interpretation", "Meaning",
        "Reflection", "Commentary", everything from that line onward is dropped to
        keep dream_text focused on the dream itself.
    """
    text = pdf_text or ""

    # Infer title if not provided (from headers like "N. <something>.pdf")
    if title_pdf is None:
        m_title = re.search(r"^\s*\d+\.\s+(.+?\.pdf)\s*$", text, flags=re.MULTILINE)
        title_pdf = m_title.group(1).strip() if m_title else "Unknown.pdf"

    lines_all = [ln.rstrip("\n") for ln in text.splitlines()]

    def value_after(label: str) -> str:
        """Return value after 'Label:' on same line or the next non-empty line."""
        label_lc = label.lower()
        for i, ln in enumerate(lines_all):
            s = ln.strip()
            if s.lower().startswith(label_lc):
                parts = s.split(":", 1)
                if len(parts) == 2 and parts[1].strip():
                    return parts[1].strip()
                for j in range(i + 1, len(lines_all)):
                    v = lines_all[j].strip()
                    if v:
                        return v
        return ""

    date = value_after("Date of dream:")
    state_of_mind = value_after("State of mind:")

    # 1) Slice the "Dream and analysis" section
    def extract_dream_section(lines: List[str]) -> List[str]:
        header_patterns = [
            r"^\s*dream\s*&?\s*analysis\b.*$",
            r"^\s*dream\s+and\s+analysis\b.*$",
            r"^\s*dreams?\b.*$",  # loose fallback
        ]
        for pat in header_patterns:
            for i, ln in enumerate(lines):
                if re.match(pat, ln.strip(), flags=re.IGNORECASE):
                    return lines[i + 1 :]
        return lines[:]  # fallback

    dream_lines = extract_dream_section(lines_all)
    dream_block = "\n".join(dream_lines).strip()

    # 2) Split into sub-dreams
    BOUNDARY_MAIN = re.compile(
        r"(?im)^\s*(?:"
        r"(?:the\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+dream\b.*|"  # ordinals
        r"dream\s*(?:no\.?|#|number)?\s*\d+\b.*|"   # "Dream 1", "Dream #2"
        r"(?:giấc\s*mơ)\s*\d+\b.*|"                 # VN: "Giấc mơ 1"
        r"(?:another|next)\s+dream\b.*|"            # "Another dream"
        r"dream\s*:\s*.*"                           # "Dream: ..."
        r")\s*$"
    )
    ENUM_LINE = re.compile(r"(?m)^\s*\d+[\.\)]\s+.*$")  # "1. ...", "2) ..."

    def split_subdreams(block_text: str) -> List[str]:
        lines = block_text.splitlines()
        idxs = [i for i, ln in enumerate(lines) if BOUNDARY_MAIN.match(ln)]
        if idxs:
            idxs.append(len(lines))
            segs = []
            for i in range(len(idxs) - 1):
                seg = "\n".join(lines[idxs[i] + 1 : idxs[i + 1]]).strip()
                if seg:
                    segs.append(seg)
            return segs

        # Fallback: plain numeric enumeration, only if there are at least two items
        enum_idxs = [i for i, ln in enumerate(lines) if ENUM_LINE.match(ln)]
        if len(enum_idxs) >= 2:
            enum_idxs.append(len(lines))
            segs = []
            for i in range(len(enum_idxs) - 1):
                seg = "\n".join(lines[enum_idxs[i] + 1 : enum_idxs[i + 1]]).strip()
                if seg:
                    segs.append(seg)
            return segs

        return [block_text.strip()] if block_text.strip() else []

    segments = split_subdreams(dream_block)

    # 3) Drop "Analysis/Interpretation/..." inside each segment
    ANALYSIS_RE = re.compile(r"(?im)^\s*(analysis|interpretation|meaning|reflection|commentary)\b[:\-]?\s*")
    def strip_analysis(segment_text: str) -> str:
        lines = segment_text.splitlines()
        for i, ln in enumerate(lines):
            if ANALYSIS_RE.match(ln):
                lines = lines[:i]
                break
        return "\n".join(l.rstrip() for l in lines).strip()

    dreams: List[Dict[str, str]] = []
    for k, seg in enumerate(segments, start=1):
        dream_text = strip_analysis(seg)
        if not dream_text:
            continue
        dreams.append({
            "case_id": case_id,
            "dream_id": f"D{k:04d}",
            "date": date,
            "dream_text": dream_text,
            "state_of_mind": state_of_mind,
            "notes": f"From PDF: {title_pdf}",
        })

    return dreams

def update_dreams(dreams: Iterable[Dream]) -> List[Dream]:
    return [
        d.model_copy(update={"dream_text": clean_dream_text(d.dream_text)})
        for d in dreams
    ]

def clean_dream_text(s: str) -> str:
    if not s:
        return ""
    # Normalize newlines and spaces
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\u00A0", " ")             # non-breaking space -> normal space
    s = re.sub(r"[ \t]+", " ", s)            # collapse runs of spaces/tabs
    s = "\n".join(line.strip() for line in s.split("\n"))  # trim each line
    s = s.replace("\n", " ")               # replace newlines with spaces
    s = re.sub(r" +", " ", s)               # collapse multiple spaces
    s = s.strip()
      
    # Strip enclosing triple quotes: """ ... """
    m = re.fullmatch(r'\s*"""\s*([\s\S]*?)\s*"""\s*', s)
    if m:
        s = m.group(1).strip()

    # Strip enclosing single double-quotes: " ... "
    m = re.fullmatch(r'\s*"\s*([\s\S]*?)\s*"\s*', s)
    if m:
        s = m.group(1).strip()
        
    return s

def int_to_rgb(v: int):
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255)

def is_black(color_int: int, tol: int = 0) -> bool:
    """Return True if color is black; with tolerance for 'near-black'."""
    r, g, b = int_to_rgb(color_int or 0)
    return r <= tol and g <= tol and b <= tol

def hex_of(v: int):
    r,g,b = int_to_rgb(v)
    return f"#{r:02X}{g:02X}{b:02X}"

def looks_bold_by_font(font_name: str) -> bool:
    if not font_name:
        return False
    f = font_name.lower()
    return any(k in f for k in BOLD_KEYWORDS)

def looks_heading_all_caps(text: str, min_len: int = 4, ratio: float = 0.8) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < min_len:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return (upper / len(letters)) >= ratio

BOLD_KEYWORDS = (
    "bold", "semibold", "demibold", "demi-bold",
    "extrabold", "extra-bold", "ultrabold", "heavy", "black"
)

