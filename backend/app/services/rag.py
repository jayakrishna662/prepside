import base64
import logging
import uuid
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.llm import get_llm
from app.services.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.retriever import (
    RetrievedChunk,
    find_mentioned_document,
    get_document_chunks,
    hybrid_retrieve,
    wants_whole_document,
)
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

NOT_FOUND_MESSAGE = "I couldn't find this in your documents."


class LLMAnswer(BaseModel):
    found: bool
    answer: str
    sources: list[int]


@dataclass
class Citation:
    document_id: uuid.UUID
    filename: str
    page: int
    has_image: bool = False


@dataclass
class Answer:
    answer: str
    found: bool
    citations: list[Citation] = field(default_factory=list)
    top_score: float = 0.0
    reason: str = "ok"
    mode: str = "search"
    images: int = 0


def _finish(question: str, answer: Answer) -> Answer:
    logger.info(
        "RAG question=%r mode=%s top_score=%.3f images=%d found=%s reason=%s",
        question,
        answer.mode,
        answer.top_score,
        answer.images,
        answer.found,
        answer.reason,
    )
    return answer


def _not_found(top_score: float, reason: str, mode: str = "search", images: int = 0) -> Answer:
    return Answer(NOT_FOUND_MESSAGE, False, [], top_score, reason, mode, images)


def _page_images(chunks: list[RetrievedChunk]) -> list[tuple[int, int, bytes]]:
    """Page pictures to attach: (source id, page, png bytes).

    Only picture chunks near the top of the results are used, and at most a few."""
    storage = get_storage()
    images: list[tuple[int, int, bytes]] = []
    seen: set[str] = set()

    for source_id, c in enumerate(chunks[: settings.image_rank_window], start=1):
        if c.kind == "text" or not c.asset_path or c.asset_path in seen:
            continue
        if len(images) >= settings.max_images_per_question:
            break
        try:
            png = storage.download(c.asset_path)
        except Exception:
            logger.warning("Could not load page picture %s", c.asset_path, exc_info=True)
            continue
        seen.add(c.asset_path)
        images.append((source_id, c.page, png))

    return images


def _build_message(text: str, images: list[tuple[int, int, bytes]]) -> HumanMessage:
    if not images:
        return HumanMessage(content=text)

    parts: list[dict] = [{"type": "text", "text": text}]
    for source_id, page, png in images:
        encoded = base64.b64encode(png).decode("ascii")
        parts.append(
            {
                "type": "text",
                "text": f"Picture of page {page} (source {source_id} comes from this page):",
            }
        )
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}})
    return HumanMessage(content=parts)


def answer_question(
    db: Session,
    user_id: uuid.UUID,
    question: str,
    student_message: str | None = None,
) -> Answer:
    chunks = None
    mode = "search"
    top_score = 0.0

    # Whole-document mode: the student names one of their files and asks for a count, list or summary
    request_text = f"{student_message or ''} {question}"
    if wants_whole_document(request_text):
        doc = find_mentioned_document(db, user_id, request_text)
        if doc is not None:
            chunks = get_document_chunks(
                db, user_id, doc.id, settings.whole_document_max_chunks
            )
            if chunks is not None:
                mode = "whole_document"

    if chunks is None:
        chunks = hybrid_retrieve(db, user_id, question, top_k=settings.retrieval_top_k)
        scores = [c.vector_score for c in chunks if c.vector_score is not None]
        top_score = max(scores, default=0.0)

        # Check 1: nothing close enough in meaning, so don't call the LLM
        if not chunks or top_score < settings.relevance_threshold:
            return _finish(question, _not_found(top_score, "below_threshold"))

    # The second look: attach page pictures when picture chunks rank near the top
    images = [] if mode == "whole_document" else _page_images(chunks)

    prompt_text = build_user_prompt(
        question,
        chunks,
        student_message,
        complete_document=(mode == "whole_document"),
    )
    result = (
        get_llm()
        .with_structured_output(LLMAnswer)
        .invoke([SystemMessage(content=SYSTEM_PROMPT), _build_message(prompt_text, images)])
    )

    # Check 2: the LLM itself says the sources don't contain the answer
    if result is None or not result.found:
        return _finish(question, _not_found(top_score, "llm_not_found", mode, len(images)))

    found_citations: dict[tuple[uuid.UUID, int], Citation] = {}
    for n in result.sources:
        if 1 <= n <= len(chunks):
            c = chunks[n - 1]
            key = (c.document_id, c.page)
            if key not in found_citations:
                found_citations[key] = Citation(c.document_id, c.filename, c.page)
            if c.asset_path:
                found_citations[key].has_image = True
    citations = list(found_citations.values())

    # Check 3: no valid citation, so we can't show where the answer came from
    if not citations:
        return _finish(question, _not_found(top_score, "no_valid_citation", mode, len(images)))

    return _finish(
        question,
        Answer(result.answer, True, citations, top_score, "ok", mode, len(images)),
    )