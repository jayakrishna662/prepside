import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.api.schemas import AskIn, ConversationOut, MessageOut
from app.db.models import Conversation, Message
from app.db.session import get_db
from app.services.chat import ask

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_conversation(
    db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.post("", response_model=ConversationOut, status_code=201)
def create_conversation(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    conv = Conversation(user_id=user_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .where(Conversation.id.in_(select(Message.conversation_id)))
        .order_by(desc(Conversation.updated_at))
    ).all()


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    _get_conversation(db, user_id, conversation_id)
    return db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    ).all()


@router.post("/{conversation_id}/messages", response_model=MessageOut)
def ask_question(
    conversation_id: uuid.UUID,
    body: AskIn,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    conv = _get_conversation(db, user_id, conversation_id)
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Question is empty")

    try:
        return ask(db, user_id, conv, question)
    except Exception:
        logger.exception("Answering failed for conversation %s", conversation_id)
        db.rollback()
        raise HTTPException(
            503, "Could not generate an answer right now. Please try again."
        )


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    conv = _get_conversation(db, user_id, conversation_id)
    db.delete(conv)
    db.commit()