from pathlib import Path
from openpyxl import Workbook
import csv
from my_type import OUTPUT_PATH, Dream


BASE_DIR = Path(__file__).resolve().parent.parent

CSV_FILE = Path(OUTPUT_PATH / "clean.csv")
CSV_FIELDNAMES = ["case_id", "dream_id", "date", "dream_text", "state_of_mind", "notes"]

def write_excel(file_name: str, data: list):
  # Tạo workbook mới
  wb = Workbook()
  ws = wb.active

  ws.append(["ID", "File_Path", "Date_from_filename", "Title_guess", "Dream_Text", "Error"])

  for row in data:
    ws.append(row)
      
  # Lưu file
  wb.save(f"{OUTPUT_PATH/file_name}.xlsx")
  print(f"Excel file created: {OUTPUT_PATH/file_name}.xlsx")  
 
def write_csv(rows: list[Dream], file_name: str ):     
  csv_file = Path(OUTPUT_PATH / file_name)   
  rows = [r.model_dump() for r in rows]

  with csv_file.open(mode="a", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
    writer.writerows(rows)
  print(f"Output written to {csv_file.as_posix()}")

def initOutput(file_name):
  output_path = OUTPUT_PATH / file_name
  with open(output_path, "w", encoding="utf-8") as f:
    f.write("")
  print(f"Init output file in {output_path}")
  
def initCSV(file_name):
  csv_file = Path(OUTPUT_PATH / file_name)
  with open(csv_file, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
  print(f"Init CSV file in {csv_file.as_posix()}")

def read_rows():
  """Returns a list of dicts (each row keyed by FIELDNAMES)."""
  if not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0:
    return [] 
  with CSV_FILE.open(mode="r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    return list(reader)
  
def write_output(text: str, file_name: str = "output"):
  output_path = OUTPUT_PATH / file_name
  with open(output_path, "a", encoding="utf-8") as f:
    f.write(text)
  print(f"Output written to {output_path}")
  
def clear_output(file_name):
  output_path = OUTPUT_PATH / file_name
  with open(output_path, "w", encoding="utf-8") as f:
    f.write("")  # Ghi đè với nội dung rỗng
