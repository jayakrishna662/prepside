from dataclasses import dataclass

import pymupdf


@dataclass
class PageText:
    page: int
    text: str


def parse_pdf(data: bytes) -> tuple[list[PageText], int]:
    pages: list[PageText] = []

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise ValueError("PDF is password protected")

        page_count = doc.page_count
        for number, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                pages.append(PageText(page=number, text=text))

    if not pages:
        raise ValueError("No readable text found (the PDF may be scanned images)")

    return pages, page_count