from pdf_helper import readPdf

from pathlib import Path

from output_helper import initCSV, write_csv, write_output
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent
folder = BASE_DIR / "data/D"

if __name__ == "__main__":
  # readPdf(folder / "demo.pdf")
  data = list()
  par = str()
  num_tokens = 0
  last_dream_id = "D0000"
  now = datetime.now().strftime("%Y%m%d_%H%M%S")
  models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.0-flash"]  
  model = models[1]  
  CSV_FILENAME = f"clean_{now}_{model}.csv"
  OUTPUT_FILENAME = f"output_{now}_{model}.txt"
  initCSV(CSV_FILENAME)

  for file in folder.rglob("*"):
    if file.is_dir():
      # par = file.name
      # if len(data) > 0:
      #   file_name = "Participant" + par + "_Master"
      #   writeExcel(file_name, data)
      #   data = list()
      continue
    
    # Đoạn văn bản bạn muốn tính token
    res = readPdf("", file.name, OUTPUT_FILENAME, last_dream_id)
      
    if not res:
      continue
    
    last_dream_id = res[-1].dream_id
        
    write_csv(res, CSV_FILENAME)

    write_output("\n\n", OUTPUT_FILENAME)

  # write_output(f"Tổng số token của tất cả văn bản là: {num_tokens}")

  # if len(data) > 0:
  #     file_name = "Participant" + par + "_Master"
  #     writeExcel(file_name, data)
  #     data = list()
