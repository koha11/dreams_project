from pathlib import Path
from pdf_helper import readPdf
from output_helper import initCSV, initOutput, write_csv, write_output
from datetime import datetime

from my_type import CHOOSEN_MODEL, INPUT_PATH, OUTPUT_PATH

if __name__ == "__main__":
  # readPdf(folder / "demo.pdf")
  data = list()
  par = str()
  num_tokens = 0
  last_case_id = "C0215" # C0001 - C0093 | C0094 - C0176 | C0177
  now = datetime.now().strftime("%Y%m%d_%H%M%S")
  count = 0
  sub_folder = ""
  is_start = False
  total_files = sum(1 for _ in INPUT_PATH.rglob("*") if _.is_file())

  CSV_FILENAME = f"clean_{now}_{CHOOSEN_MODEL.value}.csv"
  CSV_FILENAME = f"test.csv"
  CSV_FILENAME = f"4_trinh_dreams.csv"

  OUTPUT_FILENAME = f"output_{now}_{CHOOSEN_MODEL.value}.txt"
  OUTPUT_FILENAME = f"output_test.txt"
  OUTPUT_FILENAME = f"output_4_trinh_dreams.txt"
  
  START_FROM_FILE = "When I was pregnant I had a dream about eating chicken"
  
  if(START_FROM_FILE == ""):
    is_start = True

  if not Path(OUTPUT_PATH / CSV_FILENAME).exists():
    initCSV(CSV_FILENAME)
    
  if not Path(OUTPUT_PATH / OUTPUT_FILENAME).exists():
    initOutput(OUTPUT_FILENAME)

  for file in INPUT_PATH.rglob("*"):
    if file.is_dir():
      # sub_folder = file.name
      continue
    
    count += 1
    print(f"Processing file {count}/{total_files}: {file.name} ...")

    if not is_start and file.name.find(START_FROM_FILE) >= 0:
      is_start = True
      continue
    
    if not is_start:
      print(f"Skipping file {file.name} ...")
      continue
        
    res = readPdf("", file.name, OUTPUT_FILENAME, last_case_id)
      
    if not res:
      continue
    
    last_case_id = res[-1].case_id
        
    write_csv(res, CSV_FILENAME)
    write_output("\n\n", OUTPUT_FILENAME)
