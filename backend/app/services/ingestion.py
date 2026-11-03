import logging
import threading
import uuid

from sqlalchemy import delete

from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.services.chunker import chunk_pages
from app.services.embedder import embed_texts
from app.services.parser import parse_pdf
from app.services.storage import get_storage
from app.services.vision import build_visual_chunks

logger = logging.getLogger(__name__)


def _set_status(db, doc: Document, status: str, **fields) -> None:
    doc.status = status
    for key, value in fields.items():
        setattr(doc, key, value)
    db.commit()


def ingest_document(document_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return

        try:
            data = get_storage().download(doc.storage_path)

            _set_status(db, doc, "parsing")
            pages, page_count = parse_pdf(data)
            doc.page_count = page_count

            _set_status(db, doc, "chunking")
            text_chunks = chunk_pages(pages)

            _set_status(db, doc, "describing", chunks_total=0, chunks_done=0)

            def on_visual_progress(done: int, total: int) -> None:
                doc.chunks_total = total
                doc.chunks_done = done
                db.commit()

            visual_chunks = build_visual_chunks(
                data, doc.user_id, doc.id, on_progress=on_visual_progress
            )

            # Each row: (chunk_index, page, content, kind, asset_path)
            rows = [(c.chunk_index, c.page, c.content, "text", None) for c in text_chunks]
            offset = len(rows)
            rows += [
                (offset + i, v.page, v.content, v.kind, v.asset_path)
                for i, v in enumerate(visual_chunks)
            ]

            _set_status(db, doc, "embedding", chunks_total=len(rows), chunks_done=0)

            def on_progress(done: int) -> None:
                doc.chunks_done = done
                db.commit()

            vectors = embed_texts([r[2] for r in rows], on_progress=on_progress)

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


_INGEST_LOCK = threading.Lock()


def ingest_document_queued(document_id: uuid.UUID) -> None:
    # Only one document is processed at a time, to stay under the rate limits
    with _INGEST_LOCK:
        ingest_document(document_id)