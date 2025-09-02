from pathlib import Path
from openpyxl import Workbook

BASE_DIR = Path(__file__).resolve().parent.parent
folder = BASE_DIR / "outputs"

def writeExcel(file_name: str, data: list):
  # Tạo workbook mới
  wb = Workbook()
  ws = wb.active

  ws.append(["ID", "File_Path", "Date_from_filename", "Title_guess", "Dream_Text", "Error"])

  for row in data:
    ws.append(row)
      
  # Lưu file
  wb.save(f"{folder/file_name}.xlsx")
  print(f"Excel file created: {folder/file_name}.xlsx")
