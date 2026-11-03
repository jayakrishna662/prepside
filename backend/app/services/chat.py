import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message
from app.services.rag import answer_question
from app.services.rewriter import MAX_HISTORY_MESSAGES, condense_question


def get_history(db: Session, conversation_id: uuid.UUID) -> list[tuple[str, str]]:
    rows = db.execute(
        select(Message.role, Message.content)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
    ).all()
    return [(role, content) for role, content in reversed(rows)]


def ask(
    db: Session,
    user_id: uuid.UUID,
    conversation: Conversation,
    question: str,
) -> Message:
    # The caller must already have checked that this conversation belongs to user_id
    history = get_history(db, conversation.id)
    standalone = condense_question(history, question)
    answer = answer_question(db, user_id, standalone, student_message=question)

    user_msg = Message(conversation_id=conversation.id, role="user", content=question)
    db.add(user_msg)
    db.flush()  # write the question first, so the answer gets a later timestamp

    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer.answer,
        found=answer.found,
        citations=[
            {"document_id": str(c.document_id), "filename": c.filename, "page": c.page,"has_image": c.has_image,}
            for c in answer.citations
        ],
    )
    db.add(assistant_msg)

    if not history:
        conversation.title = question.strip()[:60] or "New chat"
    conversation.updated_at = func.now()

    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg