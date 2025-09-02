from pdf_helper import readPdf

from pathlib import Path

from excel_helper import writeExcel

BASE_DIR = Path(__file__).resolve().parent.parent
folder = BASE_DIR / "data"

if __name__ == "__main__":
  # readPdf(folder / "demo.pdf")
  data = list()
  par = str()
  for file in folder.rglob("*"):
    if file.is_dir():
      par = file.name
      if len(data) > 0:
        file_name = "Participant" + par + "_Master"
        writeExcel(file_name, data)
        data = list()
      continue
    data.append(readPdf(par, file.name))
    
  if len(data) > 0:
      file_name = "Participant" + par + "_Master"
      writeExcel(file_name, data)
      data = list()
