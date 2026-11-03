import time
from collections import deque
from typing import Callable

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings

EMBED_MODEL = "models/gemini-embedding-001"
EMBED_DIM = 1536
BATCH_SIZE = 30
RATE_LIMIT_PER_MIN = 90  # free tier error showed a limit of 100/min, stay below it
MAX_RETRIES = 5


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=EMBED_MODEL,
        google_api_key=settings.google_api_key,
    )


def _wait_for_quota(sent: deque, n: int) -> None:
    """Wait until sending n more chunks stays under the per-minute limit."""
    while True:
        now = time.monotonic()
        while sent and now - sent[0][0] >= 60:
            sent.popleft()
        if sum(count for _, count in sent) + n <= RATE_LIMIT_PER_MIN:
            return
        time.sleep(60 - (now - sent[0][0]) + 1)


def _embed_batch(emb, batch: list[str]) -> list[list[float]]:
    for attempt in range(MAX_RETRIES):
        try:
            return emb.embed_documents(batch, output_dimensionality=EMBED_DIM)
        except Exception:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(5 * 2**attempt)


def embed_texts(
    texts: list[str],
    on_progress: Callable[[int], None] | None = None,
) -> list[list[float]]:
    emb = get_embeddings()
    vectors: list[list[float]] = []
    sent: deque = deque()

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]

        _wait_for_quota(sent, len(batch))
        sent_at = time.monotonic()
        vectors.extend(_embed_batch(emb, batch))
        sent.append((sent_at, len(batch)))

        if on_progress:
            on_progress(len(vectors))

    return vectors



def embed_query(text: str) -> list[float]:
    emb = get_embeddings()
    for attempt in range(MAX_RETRIES):
        try:
            return emb.embed_query(text, output_dimensionality=EMBED_DIM)
        except Exception:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(5 * 2**attempt)