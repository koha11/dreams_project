from pathlib import Path
import re
import fitz  # PyMuPDF

BASE_DIR = Path(__file__).resolve().parent.parent
folder = BASE_DIR / "data"

def readPdf(sub_folder, file_name):
    id, file_path, date_from_filename, title_guess, dream_text, error = (None, None, None, None, None, None)
    file_path: Path = folder / sub_folder / file_name
    doc = fitz.open(file_path)
    id, date_from_filename, title_guess = parse_filename(file_name)
    text = ""
    for i, page in enumerate(doc):
        text += page.get_text()
        
    dream_text = extract_clean_block(text)
        
    file_path = file_path.as_posix()
    return id, file_path, date_from_filename, title_guess, dream_text, error

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
    Trả về đoạn từ 'Dream and analysis' đến trước 'student note'.
    Nếu remove_noise=True, sẽ cắt bỏ khúc nhiễu ( (https... ) -> ... -> dòng '1/2' ).
    """
    if not text:
        return None
    
    # Regex marker (không phân biệt hoa thường, theo dòng)
    RX_START = re.compile(r'(?im)^\s*Dream and analysis\b.*$')     # dòng bắt đầu
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
    return block.replace("Dream and analysis", "").strip()

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
    