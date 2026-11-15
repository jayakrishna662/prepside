# chat.py file manages the chat workflow: it retrieves conversation history, 
# rewrites the user's question if needed, gets an answer using RAG, 
# saves both the user's question and the assistant's answer in the database, 
# and updates the conversation title and timestamp.
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message
from app.services.rag import answer_question
from app.services.rewriter import MAX_HISTORY_MESSAGES, condense_question


# retrieve the most recent messages from a conversation in the database 
# and return them in chronological order (oldest to newest)
# so the application can understand the previous context of the chat.
# limited to MAX_HISTORY_MESSAGES (defined in rewriter.py)
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

    # Step 1: Get the recent messages of this chat
    history = get_history(db, conversation.id)

    # Step 2: Turn follow-up questions into a full question
    # (e.g. "explain more" -> "explain more about indexing in SQL")
    standalone = condense_question(history, question)

    # Step 3: Search the student's documents and generate the answer
    answer = answer_question(db, user_id, standalone, student_message=question)

    # Step 4: Save the student's question first
    user_msg = Message(conversation_id=conversation.id, role="user", content=question)
    db.add(user_msg)
    db.flush()  # write the question first, so the answer gets a later timestamp

     # Step 5: Save the AI's answer with its sources (citations)
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


    # Step 6: If this is the first message, use the question as the chat title (max 60 characters)
    if not history:
        conversation.title = question.strip()[:60] or "New chat"
    conversation.updated_at = func.now()

    # Step 7: Save everything to the database together
    db.commit()
    # reload the message so it has the latest saved values
    db.refresh(assistant_msg)
    return assistant_msg