#helps create a class for storing page information.
from dataclasses import dataclass

# library used to open and read PDF files.
import pymupdf


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

    # If the list is empty, no readable text was extracted from any page, so the function raises an error.
    if not pages:
        raise ValueError("No readable text found (the PDF may be scanned images)")

    return pages, page_count