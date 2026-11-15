import time
from collections import deque
from typing import Callable

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings

# Configuration variables
EMBED_MODEL = "models/gemini-embedding-001" # Specifies which embedding model to use.
EMBED_DIM = 1536 # Sets the output vector size to 1,536 numbers.
BATCH_SIZE = 30 # Processes up to 30 text chunks in one API request.
RATE_LIMIT_PER_MIN = 90  # Send at most 90 chunks per minute, free tier error showed a limit of 100/min, stay below it
MAX_RETRIES = 5 # Allows up to five attempts when an embedding request fails.


# Creates and returns a Google embedding model object configured with the model name and API key.
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=EMBED_MODEL,
        google_api_key=settings.google_api_key,
    )

# Prevents the application from sending too many text inputs to Google's embedding API within one minute.
# sent -> A deque that stores the time of previous batches and how many text inputs each batch contained.
# n ->  how many chunks we want to send now (the next batch).
def _wait_for_quota(sent: deque, n: int) -> None:
    """Wait until sending n more chunks stays under the per-minute limit."""
    # It keeps track of what was sent in the last 60 seconds, and sleeps if the next batch would go over the limit.
    # after 60 seconds finished it checks again ,finds the old batch expired, and lets the new one through.
    while True:
        now = time.monotonic() # Current time in seconds
        while sent and now - sent[0][0] >= 60:
            sent.popleft()
        if sum(count for _, count in sent) + n <= RATE_LIMIT_PER_MIN:
            return
        time.sleep(60 - (now - sent[0][0]) + 1)

# handles failed API requests.
# a request might fail because of a temporary network issue, server error, or another API problem. 
# This function retries the request, waiting longer after each failure.
def _embed_batch(emb, batch: list[str]) -> list[list[float]]:
    for attempt in range(MAX_RETRIES):
        try:
            return emb.embed_documents(batch, output_dimensionality=EMBED_DIM)
        except Exception:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(5 * 2**attempt)

# convert a list of text chunks into numerical embeddings in batches,
#  while managing API rate limits, retrying failed requests, and reporting progress.
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


# convert a user's search query into a numerical embedding vector
def embed_query(text: str) -> list[float]:
    emb = get_embeddings()
    for attempt in range(MAX_RETRIES):
        try:
            return emb.embed_query(text, output_dimensionality=EMBED_DIM)
        except Exception:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(5 * 2**attempt)