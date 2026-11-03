from dataclasses import dataclass

import pymupdf

MIN_DRAWINGS = 10  # a chart or flowchart is made of many small shapes
MIN_IMAGE_SIZE = 50  # points; smaller images (logos, icons) are ignored


@dataclass
class VisualPage:
    page: int
    images: int
    drawings: int


def find_visual_pages(data: bytes) -> list[VisualPage]:
    pages: list[VisualPage] = []

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for number, page in enumerate(doc, start=1):
            images = 0
            for info in page.get_image_info():
                x0, y0, x1, y1 = info["bbox"]
                if (x1 - x0) >= MIN_IMAGE_SIZE and (y1 - y0) >= MIN_IMAGE_SIZE:
                    images += 1

            drawings = len(page.get_drawings())

            if images > 0 or drawings >= MIN_DRAWINGS:
                pages.append(VisualPage(number, images, drawings))

    return pages


RENDER_DPI = 220  # starting value; higher means a sharper picture but more tokens for Gemini
MAX_SIDE_PX = 2600  # safety limit so a huge page cannot use too much memory


def iter_page_pngs(data: bytes, page_numbers: list[int]):
    """Yield (page_number, png_bytes) for each requested page (page numbers start at 1)."""
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for number in page_numbers:
            page = doc[number - 1]
            longest_side_pt = max(page.rect.width, page.rect.height)
            scale = min(RENDER_DPI / 72, MAX_SIDE_PX / longest_side_pt)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
            yield number, pix.tobytes("png")