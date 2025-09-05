from pdf_helper import readPdf

from pathlib import Path

from output_helper import clear_csv, clear_output, write_csv, write_excel,write_output

BASE_DIR = Path(__file__).resolve().parent.parent
folder = BASE_DIR / "data/sample"

if __name__ == "__main__":
  # readPdf(folder / "demo.pdf")
  data = list()
  par = str()
  num_tokens = 0
  last_dream_id = "D0000"
  clear_output()
  clear_csv()

  for file in folder.rglob("*"):
    if file.is_dir():
      # par = file.name
      # if len(data) > 0:
      #   file_name = "Participant" + par + "_Master"
      #   writeExcel(file_name, data)
      #   data = list()
      continue
    
    # Đoạn văn bản bạn muốn tính token
    res = readPdf("", file.name,last_dream_id)
      
    if not res:
      continue
    
    last_dream_id = res[-1].dream_id
    
    write_csv(res)

    write_output("\n\n")

  # write_output(f"Tổng số token của tất cả văn bản là: {num_tokens}")

  # if len(data) > 0:
  #     file_name = "Participant" + par + "_Master"
  #     writeExcel(file_name, data)
  #     data = list()
