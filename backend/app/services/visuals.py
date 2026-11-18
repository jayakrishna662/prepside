# The visuals.py file identifies PDF pages that may contain images,
# then converts selected pages into PNG images
#  so the application can analyze their visual content using Gemini.
from collections import Counter
from dataclasses import dataclass

import pymupdf

MIN_IMAGE_SIZE = 100  # points; smaller images (logos, icons) are ignored
MIN_PAGE_SHARE = 0.03  # an image must cover at least 3% of the page to be meaningful
MAX_PAGE_SHARE = 0.85  # an image bigger than this is probably a scanned page, skipped for now
LOGO_REPEAT = 0.3  # an image that appears on more than 30% of pages is a logo or watermark


# Holds the details of one page that has visuals
@dataclass
class VisualPage:
    page: int
    images: int
    score: float  # how much of the page the images cover, used to pick the best pages


# identifies pages that contain sufficiently large images.
def find_visual_pages(data: bytes) -> list[VisualPage]:
    # if the file is broken, there is nothing to process
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        return []

    pages: list[VisualPage] = []

    with doc:
        # password-protected files cannot be read
        if doc.needs_pass:
            return []

        total = len(doc)

        # count on how many pages each image appears
        counts = Counter()
        for page in doc:
            for xref in {img[0] for img in page.get_images(full=True)}:
                counts[xref] += 1

        # images repeated on many pages are logos or watermarks, so we ignore them
        logos = {x for x, n in counts.items() if total >= 4 and n / total > LOGO_REPEAT}

        for number, page in enumerate(doc, start=1):
            page_area = page.rect.width * page.rect.height
            images = 0
            score = 0.0

            for info in page.get_image_info(xrefs=True):
                if info["xref"] in logos:
                    continue

                x0, y0, x1, y1 = info["bbox"]
                width, height = x1 - x0, y1 - y0

                # skip small images (icons, bullets)
                if width < MIN_IMAGE_SIZE or height < MIN_IMAGE_SIZE:
                    continue

                # skip images that are too small or too big compared to the page
                share = (width * height) / page_area
                if share < MIN_PAGE_SHARE or share > MAX_PAGE_SHARE:
                    continue

                images += 1
                score += share

            # if a page contains at least one meaningful image, it qualifies for further visual processing.
            if images > 0:
                pages.append(VisualPage(number, images, score))

    return pages


RENDER_DPI = 220  # starting value; higher means a sharper picture but more tokens for Gemini
MAX_SIDE_PX = 2600  # safety limit so a huge page cannot use too much memory

# turns the chosen PDF pages into PNG images,
def iter_page_pngs(data: bytes, page_numbers: list[int]):
    """Yield (page_number, png_bytes) for each requested page (page numbers start at 1)."""
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for number in page_numbers:
            page = doc[number - 1]
            longest_side_pt = max(page.rect.width, page.rect.height)
            scale = min(RENDER_DPI / 72, MAX_SIDE_PX / longest_side_pt)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
            yield number, pix.tobytes("png")