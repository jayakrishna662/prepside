import hashlib
import os
import uuid

import logging

logger = logging.getLogger(__name__)

from sqlalchemy import desc, select
from app.api.schemas import DocumentOut

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.config import settings
from app.db.models import Chunk, Document
from app.db.session import get_db
from app.services.ingestion import ingest_document_queued
from app.services.storage import get_storage

from urllib.parse import quote

from fastapi import Response

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=202)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)

    if len(data) > max_bytes:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "Only PDF files are supported")

    file_hash = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(Document).where(
            Document.user_id == user_id, Document.file_hash == file_hash
        )
    )
    if existing:
        raise HTTPException(
            409,
            detail={
                "message": "You already uploaded this file",
                "document_id": str(existing.id),
            },
        )

    doc_id = uuid.uuid4()
    path = f"{user_id}/{doc_id}.pdf"
    get_storage().save(path, data)

    doc = Document(
        id=doc_id,
        user_id=user_id,
        filename=os.path.basename(file.filename or "document.pdf")[:255],
        storage_path=path,
        file_hash=file_hash,
        file_size=len(data),
    )
    db.add(doc)
    db.commit()

    background_tasks.add_task(ingest_document_queued, doc_id)
    return {"id": str(doc_id), "status": doc.status}



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


@router.delete("/{document_id}", status_code=204)
def delete_document(
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
    if doc.status in ACTIVE_STATUSES:
        raise HTTPException(409, "Document is still processing. Try again when it finishes.")

    asset_paths = db.scalars(
        select(Chunk.asset_path)
        .where(Chunk.document_id == doc.id, Chunk.asset_path.is_not(None))
        .distinct()
    ).all()

    storage_path = doc.storage_path
    db.delete(doc)
    db.commit()

    storage = get_storage()
    for path in [storage_path, *asset_paths]:
        try:
            storage.delete(path)
        except Exception:
            logger.warning("Could not delete file %s", path, exc_info=True)


@router.get("/{document_id}/file")
def view_document_file(
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

    try:
        data = get_storage().download(doc.storage_path)
    except FileNotFoundError:
        raise HTTPException(404, "File not found")

    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.filename)}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{document_id}/pages/{page}/image")
def view_page_image(
    document_id: uuid.UUID,
    page: int,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
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

    try:
        data = get_storage().download(path)
    except FileNotFoundError:
        raise HTTPException(404, "Page picture not found")

    return Response(
        content=data,
        media_type="image/png",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )