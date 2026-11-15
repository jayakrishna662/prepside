# Retrieves relevant document chunks using vector, keyword, or hybrid search. 
# It can also retrieve all chunks from a document when the user asks for a summary or 
# information about the entire document and then passes the retrieved content to the RAG pipeline for answer generation

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.services.embedder import embed_query


# RetrievedChunk is a data structure that stores one chunk retrieved from a document,
# along with its search scores and source information.
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


# performs vector search to find the most relevant document chunks for a user's question.
# we use cosine distance to find cosine similarity score
# because postgresql with pgvector extension doesnt have built in cosine similarity operation
def retrieve(
    db: Session,
    user_id: uuid.UUID,
    question: str,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    query_vec = embed_query(question) # Convert the question into an embedding

    # measures how far each chunk’s vector is from the question’s vector. 
    # A smaller distance means a closer meaning.
    # Cosine distance ranges from 0 to 2.
    distance = Chunk.embedding.cosine_distance(query_vec) 

    # This query asks the database for the (top_k chunks) whose meaning is closest to the question,
    # but only from this user’s documents that are finished processing.
    rows = db.execute(
        select(Chunk, Document.filename, distance.label("distance"))
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.user_id == user_id, Document.status == "ready")
        .order_by(distance)
        .limit(top_k)
    ).all()

    # Convert the results into RetrievedChunk objects and return
    return [
        RetrievedChunk(
            chunk_id=c.id,
            document_id=c.document_id,
            filename=filename,
            page=c.page,
            content=c.content,
            score=1 - dist, # cosine similarity score [-1,1]
            kind=c.kind,
            asset_path=c.asset_path,
            vector_score=1 - dist,
        )
        for c, filename, dist in rows
    ]

# finds document chunks that contain words related to the user's question
# we are using Postgres full-text search with ts_rank for keyword search
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


# hybrid_retrieve runs both searches (vector and keyword) and merges their results into one final top-5 list.
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

# If user question needs whole document to answer then return true or else false
def wants_whole_document(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in WHOLE_DOCUMENT_HINTS)


# identifies which uploaded document the user is referring to
# by checking whether its filename appears in their question.
def find_mentioned_document(
    db: Session, user_id: uuid.UUID, text: str
) -> Document | None:
    lowered = text.lower()
    best: Document | None = None  # best stores the document that matches the question.
    best_len = 0

    # This retrieves all ready documents belonging to the current user.
    docs = db.scalars(
        select(Document).where(Document.user_id == user_id, Document.status == "ready")
    ).all()

    # Check whether the filename appears in the question
    for d in docs:
        name = d.filename.lower()
        stem = name.rsplit(".", 1)[0]
        if len(stem) >= 4 and (name in lowered or stem in lowered) and len(stem) > best_len:
            best, best_len = d, len(stem)
    return best


# It fetches all the chunks of one document. It returns None if the document is empty or too big to send whole.
# This function is used when the question is about the whole document
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
            score=1.0, # we assign 1.0 because we actually not calculating relevance score, we need all chunks, so its just a placeholder
            kind=c.kind,
            asset_path=c.asset_path,
        )
        for c, filename in rows
    ]