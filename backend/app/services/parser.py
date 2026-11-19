#helps create a class for storing page information.
from dataclasses import dataclass

# library used to open and read PDF files.
import pymupdf

MIN_TEXT_CHARS = 50  # a page with fewer characters than this has no real text
SCANNED_PAGE_SHARE = 0.5  # a picture covering at least half the page means the page is a scan


# This class  holds one page’s text and its page number.
@dataclass
class PageText:
    page: int
    text: str

# This function accepts the PDF's raw data as bytes.
# Returns the list of pages with text, and the total page count
def parse_pdf(data: bytes) -> tuple[list[PageText], int]:

    #an empty list where the extracted text from each page will be stored.
    pages: list[PageText] = []

    # This opens the PDF directly from the provided bytes
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        # If the PDF requires a password to open,
        if doc.needs_pass:
            raise ValueError("PDF is password protected")
        # Get the total page count
        page_count = doc.page_count

        # Extract text from each page
        for number, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                pages.append(PageText(page=number, text=text))

    return pages, page_count



# finds scanned pages: pages with almost no text that are covered by a big picture.
# Blank pages are not included, because they have no picture.
def find_scanned_pages(data: bytes) -> list[int]:
    scanned: list[int] = []

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for number, page in enumerate(doc, start=1):
            # a page with enough real text is a normal page
            if len(page.get_text().strip()) >= MIN_TEXT_CHARS:
                continue

            # a page with almost no text, but a big picture, is a scan
            page_area = page.rect.width * page.rect.height
            for info in page.get_image_info():
                x0, y0, x1, y1 = info["bbox"]
                if ((x1 - x0) * (y1 - y0)) / page_area >= SCANNED_PAGE_SHARE:
                    scanned.append(number)
                    break

    return scanned