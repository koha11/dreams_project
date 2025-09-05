from pathlib import Path
import re
import fitz
from typing import Iterable, List, Dict, Optional

from pydantic import BaseModel

from output_helper import write_output  # PyMuPDF
from google import genai
from google.genai import types

from dotenv import load_dotenv, find_dotenv

from my_type import Dream

load_dotenv(find_dotenv())  # loads .env into process env

BASE_DIR = Path(__file__).resolve().parent.parent
folder = BASE_DIR / "data/sample"
    

def readPdf(sub_folder, file_name, last_dream_id="D0000") -> List[Dream]:
    id, file_path, date_from_filename, title_guess, dream_text, error = (None, None, None, None, None, None)
    file_path: Path = folder / sub_folder / file_name
    doc = fitz.open(file_path)
    id, date_from_filename, title_pdf = parse_filename(file_name)
    text = ""
    for i, page in enumerate(doc):
        text += page.get_text()
        # write_output(f"\n--- RAW Page {i+1} ---\n")
        # write_output(page.get_text())

    # return parse_pdf_text_to_dreams(extract_clean_block(text), title_guess)
    text = extract_clean_block(text)
    
    text = f"file: {title_pdf}\nlast dream id: {last_dream_id}\n{text}"
    
    write_output(text)
    return llm_filter_dream_text(text)
    # dream_text = extract_clean_block(text)
        
    # file_path = file_path.as_posix()
    # return id, file_path, date_from_filename, title_guess, dream_text, error

def parse_filename(file_name: str):
    # Bỏ đuôi .pdf        
    if file_name.lower().endswith(".pdf"):
        file_name = file_name[:-4]
    RX = re.compile(r"""
    ^\s*
    (?P<id>\d{1,3})          # ID ở đầu
    [\s.\-)]*                # dấu ngăn cách sau ID: space/dot/...
    (?P<code>[A-Za-z]+)      # 1+ chữ cái (D, DL, A, ...)
    (?:[._\s]+)              # theo sau là . hoặc space hoặc _
    (?P<title>.*?)           # title (lấy ngắn nhất)
    [\s_,-]*                 # ngăn cách trước năm
    (?P<year>\d{4})          # năm 4 chữ số
    \s*                      # khoảng trắng cuối (nếu có)
    (?:\.pdf)?               # đuôi .pdf (tùy chọn để linh hoạt)
    \s*$
    """, re.VERBOSE | re.IGNORECASE)
    
    m = RX.match(file_name)
    
    if not m:
        return "", "", ""
    
    id = int(m.group("id"))
    date_from_filename = int(m.group("year"))
    # Chuẩn hoá title: đổi _ -> space, gộp khoảng trắng
    title_guess = m.group("title").replace("_", " ")
    title_guess = re.sub(r"\s+", " ", title_guess).strip()
    return id, date_from_filename, title_guess

def extract_clean_block(text: str, remove_noise=True):
    """
    Trả về đoạn từ 'State of mind' đến trước 'student note'.
    Nếu remove_noise=True, sẽ cắt bỏ khúc nhiễu ( (https... ) -> ... -> dòng '1/2' ).
    """
    if not text:
        return None
    
    # Regex marker (không phân biệt hoa thường, theo dòng)
    RX_START = re.compile(r'(?im)^\s*Date of dream\b.*$')     # dòng bắt đầu
    RX_STOP  = re.compile(r'(?im)^\s*student note\b.*$')           # dòng dừng

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

def llm_filter_dream_text(dream_text: str) -> str:
    """
    Use LLM to filter out non-dream content from dream_text.
    Placeholder function - implement LLM call as needed.
    """    
    client = genai.Client()

    config = types.GenerateContentConfig(
        system_instruction="""
        công việc của bạn là nhận dữ liệu text được đọc từ 1 file pdf (nội dung của pdf chủ yếu là về những giấc mơ), 
        và bạn có nhiệm vụ phải chắt lọc lấy đúng phần nội dung của giấc mơ trong đoạn text đó, với các yêu cầu sau:
        - tôi muốn trả về 1 mảng JSON gồm các giấc mơ có trong đoạn text trên, 
        1 giấc mơ có 6 key case_id, dream_id, date, dream_text, state_of_mind, notes, 
        với case_id mặc định là C01, notes là From PDF: title_pdf, 
        dream_id có format là Dxxxx (x là số, ví dụ D0001, D0002,...) và phải bắt đầu từ id trước đó (được cung cấp trong văn bản),
        date thì lấy theo định dạng dd/mm/yyyy,
        phần dream_text là quan trọng nhất, bạn phải lấy chính xác từng dream riêng biệt,
        và nội dung phải y hệt với văn bản gốc (loại bỏ các ký tự escapse, các từ để liệt kê như my first dream is, second dream,... hay các chỉ mục 1., 2., ...),
        """,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json",
        response_schema=list[Dream],
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite", contents=dream_text, config=config
    )    
    
    data: List[Dream] = response.parsed
    
    write_output(f"\n{response.text}\n")
        
    return update_dreams(data)

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
