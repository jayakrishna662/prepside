import logging
import threading
import uuid

from sqlalchemy import delete

from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.services.chunker import chunk_pages
from app.services.embedder import embed_texts
from app.services.ocr import ocr_pages
from app.services.parser import find_scanned_pages, parse_pdf
from app.services.storage import get_storage
from app.services.vision import build_visual_chunks

logger = logging.getLogger(__name__)

# It updates a document’s status (like “processing”, “ready” or “failed”)
# and can set extra fields(like error message when status is failed) at the same time, then saves to the database.
def _set_status(db, doc: Document, status: str, **fields) -> None:
    doc.status = status
    for key, value in fields.items():
        setattr(doc, key, value)
    db.commit()


# this function handles the complete document ingestion pipeline,
# from downloading a PDF to storing its processed chunks and embeddings in the database.
def ingest_document(document_id: uuid.UUID) -> None:
    # Open our own database session (this runs in the background after upload)
    db = SessionLocal()
    try:
        # Find the document; if it doesn't exist, stop
        doc = db.get(Document, document_id)
        if doc is None:
            return

        try:
            # Step 1: Download the file from storage
            data = get_storage().download(doc.storage_path)

                          # Step 2: Read the pages and text from the file
            _set_status(db, doc, "parsing")
            pages, page_count = parse_pdf(data)
            doc.page_count = page_count

            # Scanned pages have no real text, so the llm reads them from the picture.
            # It also describes any photo or diagram on those pages.
            scanned = find_scanned_pages(data)
            scanned_visuals = []
            if scanned:
                result = ocr_pages(data, scanned, doc.user_id, doc.id)
                by_page = {p.page: p for p in pages}
                for p in result.pages:
                    by_page[p.page] = p
                pages = [by_page[n] for n in sorted(by_page)]
                scanned_visuals = result.visuals

            # If there is still no text, the document cannot be searched
            if not pages:
                raise ValueError("No readable text found (the PDF may be scanned images)")

            # Step 3: Split the text into small chunks
            _set_status(db, doc, "chunking")
            text_chunks = chunk_pages(pages)

            # Step 4: Ask Gemini to describe charts, diagrams and images
            _set_status(db, doc, "describing", chunks_total=0, chunks_done=0)

             # Saves progress after each page, so the UI can show a progress bar
            def on_visual_progress(done: int, total: int) -> None:
                doc.chunks_total = total
                doc.chunks_done = done
                db.commit()

            visual_chunks = build_visual_chunks(
                data, doc.user_id, doc.id, on_progress=on_visual_progress
            )
            
            # Scanned pages were already handled in Step 2, so we drop them here to avoid duplicates,
            # then add the photos found on the scanned pages.
            visual_chunks = [v for v in visual_chunks if v.page not in scanned]
            visual_chunks += scanned_visuals

            # Step 5: Put text chunks and visual chunks into one list
            # Each row: (chunk_index, page, content, kind, asset_path)
            rows = [(c.chunk_index, c.page, c.content, "text", None) for c in text_chunks]
            offset = len(rows)
            rows += [
                (offset + i, v.page, v.content, v.kind, v.asset_path)
                for i, v in enumerate(visual_chunks)
            ]

            # Step 6: Turn each chunk's text into a vector (embedding)
            _set_status(db, doc, "embedding", chunks_total=len(rows), chunks_done=0)

            # Saves progress while embedding
            def on_progress(done: int) -> None:
                doc.chunks_done = done
                db.commit()

            
            vectors = embed_texts([r[2] for r in rows], on_progress=on_progress)

            # Step 7: Save the chunks and their vectors to the database
            _set_status(db, doc, "storing")
            db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
            db.add_all(
                Chunk(
                    document_id=doc.id,
                    user_id=doc.user_id,
                    chunk_index=index,
                    page=page,
                    content=content,
                    kind=kind,
                    asset_path=asset_path,
                    embedding=vector,
                )
                for (index, page, content, kind, asset_path), vector in zip(rows, vectors)
            )

            # Step 8: Done. The document can now be searched in chat
            _set_status(db, doc, "ready", error_message=None)

        except ValueError as e:
            db.rollback()
            doc = db.get(Document, document_id)
            _set_status(db, doc, "failed", error_message=str(e))

        except Exception:
            logger.exception("Ingestion failed for document %s", document_id)
            db.rollback()
            doc = db.get(Document, document_id)
            _set_status(
                db,
                doc,
                "failed",
                error_message="Processing failed. Please try again.",
            )
    finally:
        db.close()

# creates a lock that prevents multiple threads from executing the protected section simultaneously.
_INGEST_LOCK = threading.Lock()

# t runs ingest_document, but only one document at a time. 
# If other uploads arrive while one is being processed, they wait their turn.
def ingest_document_queued(document_id: uuid.UUID) -> None:
    # Only one document is processed at a time, to stay under the rate limits
    with _INGEST_LOCK:
        ingest_document(document_id)