from pathlib import Path

from app.services.ocr import _transcribe
from app.services.visuals import iter_page_pngs

# put the real path of the scanned PDF here
path = Path(r"C:\Users\Jaykr\Downloads\PublicWaterMassMailing.pdf")
PAGE = 1

data = path.read_bytes()

for number, png in iter_page_pngs(data, [PAGE]):
    text = _transcribe(png, number)
    print(f"--- Text found on page {number} ---\n")
    print(text)