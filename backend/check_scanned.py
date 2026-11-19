from pathlib import Path

from app.services.parser import find_scanned_pages

# put the real paths of your two files here
FILES = {
    "scanned": Path(r"C:\Users\Jaykr\Downloads\PublicWaterMassMailing.pdf"),
    "normal": Path(r"C:\Users\Jaykr\Downloads\Taj_Mahal.pdf"),
}

for label, path in FILES.items():
    pages = find_scanned_pages(path.read_bytes())
    print(f"{label}: {path.name} -> scanned pages {pages}")