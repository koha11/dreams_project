from collections import Counter
import math
from pathlib import Path
import re
import unicodedata as ud

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
    pdf_text_list = []
    text = ""
    is_not_dream_text = False
    
    # for i,page in enumerate(doc):
    #     data = page.get_text("dict")  # structured: blocks -> lines -> spans
    #     for block in data.get("blocks", []):
    #         if "lines" not in block:       # skip image blocks, etc.
    #             continue
    #         for line in block["lines"]:
    #             if len(pdf_text_list) > 0 and pdf_text_list[-1] != '\xa0':
    #                 pdf_text_list.append(".")
    #             for span in line["spans"]:
    #                 text  = span["text"]
    #                 flags = span.get("flags", 0)
    #                 is_bold   = bool(flags & 16)
    #                 is_italic = bool(flags & 2)
    #                 srgb = span.get("color", 0)
    #                 hex_rgb = f"#{srgb:06x}"
                    
    #                 # if hex_rgb == "#c216c2" or hex_rgb == "#ffffff":
    #                 #     is_not_dream_text = not is_not_dream_text
    #                 #     continue                                
                    
    #                 if is_all_caps(text):
    #                     continue
                    
    #                 if is_not_dream_text:                                        
    #                     continue
                    
    #                 write_output(str({
    #                     "text": text,
    #                     "font": span.get("font"),
    #                     "size": span.get("size"),
    #                     "color": hex_rgb,
    #                 }) + "\n", output_file_name)
                    
    #                 if hex_rgb == "#000000":
    #                     pdf_text_list.append(text)
                        
    
    # write_output("".join(pdf_text_list), output_file_name)
    
    for i, page in enumerate(doc): text += page.get_text()
        
    text = extract_clean_block(text)    

    text = f"title_pdf: {title_pdf}. last case id: {last_case_id}. PDF text: {text}"

    text = clean_dream_text(text)
    
    text = remove_dash_bracket_blocks(text)

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

def remove_dash_bracket_blocks(text: str) -> str:
    # Xóa mọi khối dạng [- ... ] (kể cả xuống dòng bên trong)
    BLOCK_RX = re.compile(r"\[\s*-\s*.*?\]", flags=re.DOTALL)
    
    out = BLOCK_RX.sub("", text)
    # dọn khoảng trắng thừa sau khi xóa
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.!?;:…])", r"\1", out)
    return out.strip()

def strip_allcaps_runs(text: str, min_words: int = 0) -> str:
    ALLCAPS_RUN = re.compile(
    r"""
    (                           # capture the whole run
      \b[A-Z][A-Z'’\-]+         # 1st ALL-CAPS word (len >= 2)
      (?:[ ,:;–-]+\b[A-Z][A-Z'’\-]+){2,}   # + at least 2 more ALL-CAPS words
    )
    """,
    re.VERBOSE,
    )
    
    def _repl(m):
        run = m.group(0)
        # Count words in the run (tokens with letters)
        n_words = len(re.findall(r"\b[A-Z][A-Z'’\-]+\b", run))
        return "" if n_words >= min_words else run

    out = ALLCAPS_RUN.sub(_repl, text)
    # Tidy spaces created by removals
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    
    return out.strip()

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

def srgb_hex(srgb_int: int) -> str:
    return f"#{srgb_int:06x}"

def _shear_angle_deg(transform):
    """
    transform: [a, b, c, d, e, f] từ texttrace (ma trận Tm).
    Trả về độ nghiêng (độ). Dùng cả b/a và c/d rồi lấy trị tuyệt đối lớn hơn.
    """
    a, b, c, d, _, _ = transform
    ang1 = math.degrees(math.atan2(c, d)) if abs(d) > 1e-9 else 0.0
    ang2 = math.degrees(math.atan2(b, a)) if abs(a) > 1e-9 else 0.0
    return max(abs(ang1), abs(ang2))

def _collect_italic_regions(page: fitz.Page, shear_thresh_deg: float = 7.0):
    """
    Quét texttrace để lấy các bbox có nghiêng (italic) theo ngưỡng độ.
    Trả về list các Rect (khu vực nghiêng).
    """
    italic_boxes = []
    for tr in page.get_texttrace():
        if tr.get("type") != "text":
            continue
        tf = tr.get("transform")
        if not tf:
            continue
        if _shear_angle_deg(tf) >= shear_thresh_deg:
            italic_boxes.append(fitz.Rect(tr["bbox"]))
    return italic_boxes

def spans_with_italic_only(page: fitz.Page, shear_thresh_deg: float = 7.0, use_flags_fallback: bool = False):
    """
    Trả về list spans: {text, bbox, color, size, italic}
    - italic dựa trên texttrace (shear). Không xử lý bold.
    - Tùy chọn: fallback dùng span.flags (bit 2) nếu muốn (mặc định tắt).
    """
    # 1) Lấy các vùng nghiêng từ texttrace
    italic_regions = _collect_italic_regions(page, shear_thresh_deg)

    # 2) Duyệt spans từ "dict" và gán italic nếu bbox giao với vùng nghiêng
    out = []
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for sp in line["spans"]:
                txt = sp.get("text", "")
                if not txt.strip():
                    continue
                bbox = fitz.Rect(sp["bbox"])
                italic = any(bbox.intersects(r) for r in italic_regions)

                if use_flags_fallback and not italic:
                    # bit 2 của flags thường không đáng tin trong nhiều PDF, nhưng để tùy chọn
                    italic = bool(sp.get("flags", 0) & 2)

                out.append({
                    "text": txt,
                    "bbox": sp["bbox"],
                    "size": sp.get("size"),
                    "color": f"#{sp.get('color', 0):06x}",
                    "italic": italic,
                })
    return out

def is_all_caps(text: str) -> bool:

    if not text or text.isspace() or text.isdigit() or len(text) < 2:
        return False
    
    # s = ud.normalize("NFKC", text)

    # has_letter = False    
    for ch in text[1:]:
        if not ch.isupper() and not ch in ("-", "—", "–", "'", "’", '"', "“", "”", ".", ",", "!", "?", ";", ":", "/"):
            return False
            
    return True