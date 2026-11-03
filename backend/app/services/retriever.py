import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.services.embedder import embed_query


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page: int
    content: str
    score: float  # raw score from the search that found it
    vector_score: float | None = None  # cosine similarity, if found by vector search
    rrf_score: float = 0.0  # combined score after merging
    kind: str = "text"
    asset_path: str | None = None


def retrieve(
    db: Session,
    user_id: uuid.UUID,
    question: str,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    query_vec = embed_query(question)
    distance = Chunk.embedding.cosine_distance(query_vec)

    rows = db.execute(
        select(Chunk, Document.filename, distance.label("distance"))
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.user_id == user_id, Document.status == "ready")
        .order_by(distance)
        .limit(top_k)
    ).all()

    return [
        RetrievedChunk(
            chunk_id=c.id,
            document_id=c.document_id,
            filename=filename,
            page=c.page,
            content=c.content,
            score=1 - dist,
            kind=c.kind,
            asset_path=c.asset_path,
            vector_score=1 - dist,
        )
        for c, filename, dist in rows
    ]


def keyword_search(
    db: Session,
    user_id: uuid.UUID,
    question: str,
    top_k: int = 10,
) -> list[RetrievedChunk]:
    words = [w for w in re.findall(r"\w+", question.lower()) if w != "or"]
    if not words:
        return []

    ts_query = func.websearch_to_tsquery("english", " or ".join(words))
    ts_vector = func.to_tsvector("english", Chunk.content)
    rank = func.ts_rank(ts_vector, ts_query)

    rows = db.execute(
        select(Chunk, Document.filename, rank.label("rank"))
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.user_id == user_id,
            Document.status == "ready",
            ts_vector.op("@@")(ts_query),
        )
        .order_by(rank.desc())
        .limit(top_k)
    ).all()

    return [
        RetrievedChunk(
            chunk_id=c.id,
            document_id=c.document_id,
            filename=filename,
            page=c.page,
            content=c.content,
            score=float(r),
            kind=c.kind,
            asset_path=c.asset_path,
        )
        for c, filename, r in rows
    ]


def hybrid_retrieve(
    db: Session,
    user_id: uuid.UUID,
    question: str,
    top_k: int = 5,
    candidates: int = 15,
    k: int = 60,
) -> list[RetrievedChunk]:
    vector_hits = retrieve(db, user_id, question, top_k=candidates)
    keyword_hits = keyword_search(db, user_id, question, top_k=candidates)

    merged: dict[uuid.UUID, RetrievedChunk] = {}
    points: dict[uuid.UUID, float] = {}

    for hits in (vector_hits, keyword_hits):
        for position, hit in enumerate(hits, start=1):
            points[hit.chunk_id] = points.get(hit.chunk_id, 0.0) + 1 / (k + position)
            merged.setdefault(hit.chunk_id, hit)

    ranked = sorted(merged.values(), key=lambda h: points[h.chunk_id], reverse=True)
    for h in ranked:
        h.rrf_score = points[h.chunk_id]
    return ranked[:top_k]



WHOLE_DOCUMENT_HINTS = (
    "how many",
    "list all",
    "list every",
    "all the",
    "every ",
    "summarize",
    "summarise",
    "summary",
    "overview",
    "entire",
    "whole document",
)


def wants_whole_document(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in WHOLE_DOCUMENT_HINTS)


def find_mentioned_document(
    db: Session, user_id: uuid.UUID, text: str
) -> Document | None:
    lowered = text.lower()
    best: Document | None = None
    best_len = 0

    docs = db.scalars(
        select(Document).where(Document.user_id == user_id, Document.status == "ready")
    ).all()
    for d in docs:
        name = d.filename.lower()
        stem = name.rsplit(".", 1)[0]
        if len(stem) >= 4 and (name in lowered or stem in lowered) and len(stem) > best_len:
            best, best_len = d, len(stem)
    return best


def get_document_chunks(
    db: Session, user_id: uuid.UUID, document_id: uuid.UUID, max_chunks: int
) -> list[RetrievedChunk] | None:
    rows = db.execute(
        select(Chunk, Document.filename)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.user_id == user_id,
            Chunk.document_id == document_id,
            Document.status == "ready",
        )
        .order_by(Chunk.chunk_index)
        .limit(max_chunks + 1)
    ).all()

    if not rows or len(rows) > max_chunks:
        return None  # empty, or too large to send whole

    return [
        RetrievedChunk(
            chunk_id=c.id,
            document_id=c.document_id,
            filename=filename,
            page=c.page,
            content=c.content,
            score=1.0,
            kind=c.kind,
            asset_path=c.asset_path,
        )
        for c, filename in rows
    ]