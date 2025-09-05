from pathlib import Path
from pprint import pprint
from openpyxl import Workbook
import csv
from my_type import Dream

BASE_DIR = Path(__file__).resolve().parent.parent
folder = BASE_DIR / "outputs"
CSV_FILE = Path(folder / "clean.csv")
CSV_FIELDNAMES = ["case_id", "dream_id", "date", "dream_text", "state_of_mind", "notes"]


def write_excel(file_name: str, data: list):
  # Tạo workbook mới
  wb = Workbook()
  ws = wb.active

  ws.append(["ID", "File_Path", "Date_from_filename", "Title_guess", "Dream_Text", "Error"])

  for row in data:
    ws.append(row)
      
  # Lưu file
  wb.save(f"{folder/file_name}.xlsx")
  print(f"Excel file created: {folder/file_name}.xlsx")  
 
def write_csv(rows: list[Dream]):
  """
  rows: iterable of dicts where keys match FIELDNAMES
  Creates the file and writes a header if it doesn't exist or is empty.
  """
    
  rows = [r.model_dump() for r in rows]
  
  with CSV_FILE.open(mode="a", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)      
    writer.writerows(rows)
  print(f"Output written to {CSV_FILE.name}")

def clear_csv():
  with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
  print(f"Output written to {CSV_FILE.name}")

def read_rows():
  """Returns a list of dicts (each row keyed by FIELDNAMES)."""
  if not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0:
    return [] 
  with CSV_FILE.open(mode="r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    return list(reader)
  
def write_output(text: str, file_name: str = "output.txt"):
  output_path = folder / file_name
  with open(output_path, "a", encoding="utf-8") as f:
    f.write(text)
  print(f"Output written to {output_path}")
  
def clear_output(file_name: str = "output.txt"):
  output_path = folder / file_name
  with open(output_path, "w", encoding="utf-8") as f:
    f.write("")  # Ghi đè với nội dung rỗng
  print(f"Output file cleared: {output_path}")
