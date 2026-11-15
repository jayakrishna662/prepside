import hashlib
import logging
import os
import uuid

# Create a logger object for this file
# When a message gets logged, the log line can show which file it came from.
# This makes debugging much easier:
logger = logging.getLogger(__name__)

from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.api.schemas import DocumentOut
from app.core.config import settings
from app.db.models import Chunk, Document
from app.db.session import get_db
from app.services.ingestion import ingest_document_queued
from app.services.storage import get_storage

# Create a router that holds a set of endpoints
# Every endpoint on this router automatically gets /documents added to the front of its URL.
router = APIRouter(prefix="/documents", tags=["documents"])



# “When someone sends a POST request to /documents, run the function below. 
# Reply with status 202, which means ‘accepted, still working on it’.”
@router.post("", status_code=202)

# This code is a “Upload PDF” button on the server side.
# When a user sends a PDF file, the server: 
# i) Checks the file is OK (not too big, really a PDF, not a duplicate)
# ii) Saves it, records it in DB, Starts processing it in background.

def upload_document(
    background_tasks: BackgroundTasks, # A helper from FastAPI that lets us run slow jobs after replying to the user.
    file: UploadFile = File(...), # The uploaded file itself. The ... means it is required.
    db: Session = Depends(get_db), # Gives us a database connection to read and write data.
    user_id: uuid.UUID = Depends(get_current_user_id), # Finds out who is logged in and gives us their ID.
):
    max_bytes = settings.max_upload_mb * 1024 * 1024 # Converts the size limit from MB to bytes (for example, 10 MB becomes 10,485,760 bytes).
    data = file.file.read(max_bytes + 1) # Reads the file into memory, but only up to the limit plus one byte. That one extra byte is just a test: if we got it, the file is too big.

    # i) Check the PDF SIZE
    if len(data) > max_bytes:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")
    # ii) Check if its a PDF 
    # Every real PDF begins with the characters %PDF. If this file doesn’t, stop with error 400 (“bad request”).
    if not data.startswith(b"%PDF"):  
        raise HTTPException(400, "Only PDF files are supported")

    # iii) Check for duplicates 
    # Calculates a SHA-256 hash to detect duplicate uploads for the same user.
    file_hash = hashlib.sha256(data).hexdigest()

    # Asks the database: “Has this user already uploaded a file with this file_hash?”
    existing = db.scalar(
        select(Document).where(
            Document.user_id == user_id, Document.file_hash == file_hash
        )
    )
    # If yes, stop with error 409 (“conflict”) and tell them which document already exists.
    if existing:
        raise HTTPException(
            409,
            detail={
                "message": "You already uploaded this file",
                "document_id": str(existing.id),
            },
        )
    # iv) Save the File 
    # Generates a unique document ID for new document
    doc_id = uuid.uuid4()
    # Builds the storage location, like user123/abc456.pdf. Each user gets their own folder.
    path = f"{user_id}/{doc_id}.pdf"

    # Actually saves the file at that location (Storage location is defines in app/services/storage.py )
    get_storage().save(path, data)

    # v) Save to Database to create a record
    doc = Document(
        id=doc_id,
        user_id=user_id,
        filename=os.path.basename(file.filename or "document.pdf")[:255],
        storage_path=path,
        file_hash=file_hash,
        file_size=len(data),
    )
    # add puts the record in line to be saved. commit actually writes it to the database.
    db.add(doc)
    db.commit()

    # Schedules ingest_document_queued() as a background task.
    background_tasks.add_task(ingest_document_queued, doc_id)

    # Returns the document ID and its initial status(Uploaded)
    return {"id": str(doc_id), "status": doc.status}



# fetches all documents belonging to the logged-in user from the database and returns them
@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return db.scalars(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(desc(Document.created_at))
    ).all()


# fetches a specific document details from db like filename, status, page count, progress and so on.
@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    doc = db.scalar(
        select(Document).where(
            Document.id == document_id, Document.user_id == user_id
        )
    )
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


ACTIVE_STATUSES = ("uploaded", "parsing", "chunking", "describing", "embedding", "storing")


# deletes a document and its associated chunks,embeddings, Page images on disk
@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    # i) Delete document record in the db first
    # Find the document by ID and owner
    doc = db.scalar(
        select(Document).where(
            Document.id == document_id, Document.user_id == user_id
        )
    )
    if doc is None:
        raise HTTPException(404, "Document not found")

    # If the doc is still being processed in the background,
    #  deleting it would break that work, so the backend refuses with 409 Conflict.
    if doc.status in ACTIVE_STATUSES:
        raise HTTPException(409, "Document is still processing. Try again when it finishes.")

    # Find associated asset files, Some document chunks may have associated files, 
    # such as extracted images. This query retrieves the paths of those files.
    asset_paths = db.scalars(
        select(Chunk.asset_path)
        .where(Chunk.document_id == doc.id, Chunk.asset_path.is_not(None))
        .distinct()
    ).all()

    # Save the documents’s path in a variable first, because doc won’t be usable after the delete.
    storage_path = doc.storage_path
    db.delete(doc) # marks the document record for deletion.
    db.commit() # commits the database transaction.

    # ii) Delete documents & its assets from local storage 
    # retrieve the storage path of the document, 
    # because we also need to delete the PDF and its associated files from local storage.
    storage = get_storage()

    # This loop retreives all associated assets and deletes them
    for path in [storage_path, *asset_paths]:
        try:
            storage.delete(path)
        except Exception:
            logger.warning("Could not delete file %s", path, exc_info=True)


# allows a user to view an uploaded PDF in their browser.
@router.get("/{document_id}/file")
def view_document_file(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    # Find the document by ID and owner
    doc = db.scalar(
        select(Document).where(
            Document.id == document_id, Document.user_id == user_id
        )
    )
    if doc is None:
        raise HTTPException(404, "Document not found")
    
    # Read the document from storage
    try:
        data = get_storage().download(doc.storage_path)
    except FileNotFoundError:
        raise HTTPException(404, "File not found")

    # Return the PDF to the browser
    return Response(
        content=data, # The PDF bytes
        media_type="application/pdf", # Tells the browser “this is a PDF”, so it opens its built-in PDF viewer
        headers={
            # Content-Disposition": f"inline -> Tells the browser to display the PDF inside the browser 
            # filename*=UTF-8''{quote(doc.filename)} -> Provides the original filename 
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.filename)}",

            # It tells the browser “trust the type I gave you, don’t guess”. 
            # Without it, a browser could guess a file is something else (like HTML) and run it.
            "X-Content-Type-Options": "nosniff",
        },
    )


# Retrieves an image associated with a specific document page and displays it to the user.
@router.get("/{document_id}/pages/{page}/image")
def view_page_image(
    document_id: uuid.UUID,
    page: int,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    # The backend searches the chunks table for an image path
    path = db.scalar(
        select(Chunk.asset_path)
        .where(
            Chunk.document_id == document_id,
            Chunk.user_id == user_id,
            Chunk.page == page,
            Chunk.asset_path.is_not(None),
        )
        .limit(1)
    )
    if path is None:
        raise HTTPException(404, "Page picture not found")

    # Read the image from storage
    try:
        data = get_storage().download(path)
    except FileNotFoundError:
        raise HTTPException(404, "Page picture not found")

    # Return the image to the browser
    return Response(
        content=data,
        media_type="image/png", # Tells the browser that the response is a PNG image.
        headers={
            # Prevents the browser from guessing a different content type.
            "X-Content-Type-Options": "nosniff",

            # Allows a private browser cache to reuse the response for up to 3,600 seconds,
            #  or one hour, without necessarily requesting it again.
            "Cache-Control": "private, max-age=3600", 
        },
    )