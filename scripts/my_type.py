from enum import Enum
from pathlib import Path
import threading
from pydantic import BaseModel
import time
from collections import deque

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data/5. NHƯ (21 - 25) _ 113 Dreams/TỐ NHƯ 2023 _ ÂN"
OUTPUT_PATH = BASE_DIR / "outputs"

class GEMINI_MODEL(Enum):
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_2_0_FLASH_LITE = "gemini-2.0-flash-lite"
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
    
class GROQ_MODEL(Enum):
    LLAMA_3_1_8B_INSTANT = "llama-3.1-8b-instant"
    LLAMA_3_3_70B_VERSATILE = "llama-3.3-70b-versatile"

class Dream(BaseModel):
  case_id: str
  dream_id: str
  date: str
  dream_text: str
  state_of_mind: str
  notes: str
  
# --- Rate limiter chung cho toàn module ---
class RateLimiter:
    def __init__(self, max_calls: int, period_seconds: float):
        self.max_calls = max_calls
        self.period = period_seconds
        self._lock = threading.Lock()
        self._calls = deque()  # lưu các mốc thời gian của lần gọi gần nhất

    def acquire(self):
        # Chờ (nếu cần) để đảm bảo không quá max_calls trong period
        with self._lock:
            now = time.monotonic()
            # loại bỏ các lần gọi đã quá "cửa sổ" period
            while self._calls and (now - self._calls[0]) > self.period:
                self._calls.popleft()

            sleep_for = 0.0
            if len(self._calls) >= self.max_calls:
                # phải đợi đến khi lần gọi cũ nhất rơi khỏi cửa sổ
                oldest = self._calls[0]
                sleep_for = self.period - (now - oldest)

        if sleep_for > 0:
            time.sleep(sleep_for)

        # ghi nhận lần gọi mới sau khi (có thể) đã ngủ
        with self._lock:
            self._calls.append(time.monotonic())

# CHOOSEN_MODEL = GROQ_MODEL.LLAMA_3_1_8B_INSTANT
CHOOSEN_MODEL = GEMINI_MODEL.GEMINI_2_5_FLASH

# C0093