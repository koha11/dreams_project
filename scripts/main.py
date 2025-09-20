from pathlib import Path
from pdf_helper import readPdf
from output_helper import initCSV, write_csv, write_output
from datetime import datetime

from my_type import CHOOSEN_MODEL, INPUT_PATH

if __name__ == "__main__":
  # readPdf(folder / "demo.pdf")
  data = list()
  par = str()
  num_tokens = 0
  last_case_id = "C0000"
  now = datetime.now().strftime("%Y%m%d_%H%M%S")
  count = 0
  total_files = sum(1 for _ in INPUT_PATH.rglob("*") if _.is_file())

  CSV_FILENAME = f"clean_{now}_{CHOOSEN_MODEL.value}.csv"
  OUTPUT_FILENAME = f"output_{now}_{CHOOSEN_MODEL.value}.txt"
  
  if not Path(OUTPUT_FILENAME).exists():
    initCSV(CSV_FILENAME)

  for file in INPUT_PATH.rglob("*"):
    if file.is_dir():
      continue
    
    count += 1
    print(f"Processing file {count}/{total_files}: {file.name} ...")
    
    # Đoạn văn bản bạn muốn tính token
    res = readPdf("", file.name, OUTPUT_FILENAME, last_case_id)
      
    if not res:
      continue
    
    last_case_id = res[-1].case_id
        
    write_csv(res, CSV_FILENAME)
    write_output("\n\n", OUTPUT_FILENAME)
