# Shows errors and useful info in logs
import logging

# Handles unique IDs for users and conversations.
import uuid

# APIRouter --> Groups related API endpoints together.
# Depends --> Lets FastAPI provide required dependencies, such as a database session.
# HTTPException --> Returns HTTP errors, such as 404 or 400.
from fastapi import APIRouter, Depends, HTTPException

# desc --> Sorts results in descending order. select --> Builds database queries.
from sqlalchemy import desc, select

# session --> Represents a SQLAlchemy database session used to interact with the database.
from sqlalchemy.orm import Session

# Function to Find out which user is calling
from app.api.deps import get_current_user_id

# These are Pydantic schemas that define the structure of API input and output data.
from app.api.schemas import AskIn, ConversationOut, MessageOut

# These are SQLAlchemy models representing database tables.
from app.db.models import Conversation, Message

# Imports a function that provides a database session to an API endpoint.
from app.db.session import get_db

# Imports the function responsible for processing a user's question and generating an answer.
from app.services.chat import ask

# A tool to write error logs. __name__ just means “label the logs with this file’s name”.
logger = logging.getLogger(__name__)

# To group all conversation-related API endpoints together.
# prefix="/conversations"  means every endpoint here starts with /conversations
# tags=["conversations"] groups these endpoints under the conversations section in FastAPI's Swagger API documentation.
router = APIRouter(prefix="/conversations", tags=["conversations"])


# Helper Function to find a conversation in the database and make sure it belongs to the current user.
# The _ at the start means “private helper, used only inside this file”.
# The query says: “Find the chat with this id AND belonging to this user_id.”
# Found: returns the chat.   Not found: sends a 404 error.
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


# creates a new conversation in the database when the frontend sends a request to POST /conversations.
# response_model=ConversationOut tells FastAPI to validate and format the response using the ConversationOut schema.
# status_code=201 means the API returns 201 Created when the conversation is successfully created.
@router.post("", response_model=ConversationOut, status_code=201)
def create_conversation(
    # Get the database session and user ID
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    # Create a Conversation object associated with the current user.
    conv = Conversation(user_id=user_id)
    # This tells SQLAlchemy to track the new conversation and prepare to insert it into the database.
    db.add(conv)
    # saves it to the database, and the table now has a new row
    db.commit()
    # reloading the conversation object with the latest values from the database
    db.refresh(conv)
    # return converstaion object as json with the fields defined in ConversationOut schema and status 201
    return conv

# Fetches  current user's conversations that have at least one message, showing latest on top.
# This code looks into the database, picks your chats, and sends them back so the sidebar can show them.
# response_model=list[ConversationOut] means the API returns a list of conversations, formatted using the ConversationOut schema.
@router.get("", response_model=list[ConversationOut])
def list_conversations(
    # Get the database and current user
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return db.scalars( # It runs a database query and gives you back the objects instead of table rows
        select(Conversation)  # select all conversation records.
        .where(Conversation.user_id == user_id)  # only conversations belonging to the current user.
        .where(Conversation.id.in_(select(Message.conversation_id)))  # keeps only conversations whose IDs appear in the Message table. because A newly created but empty conversation won't appear in this list, so we ignore such ones.
        .order_by(desc(Conversation.updated_at)) # Sorts the conversations by updated_at, with the most recently updated ones first.
    ).all()  # collects all matching objects into a Python list.



# retrieves all messages belonging to a specific conversation of current user, in the order they were created.
# response_model=list[MessageOut] means the API returns a list of messages formatted according to the MessageOut schema.
@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    _get_conversation(db, user_id, conversation_id) # It checks whether the conversation exists and belongs to this user. If not, it raises a 404 error.
    return db.scalars(
        select(Message) # Select all Messages
        .where(Message.conversation_id == conversation_id) # selects only messages belonging to the requested conversation.
        .order_by(Message.created_at) # sorts messages from oldest to newest. so newest appears at bottom
    ).all() # Collects all matching messages as a Python list.


# It receives the question you type in the chat then validates it and sends back the answer from your documents.

@router.post("/{conversation_id}/messages", response_model=MessageOut)
def ask_question(
    conversation_id: uuid.UUID, # which conversation the question belongs to.
    body: AskIn, # the request data, validated using the AskIn schema.
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    conv = _get_conversation(db, user_id, conversation_id) # This checks that the conversation exists and belongs to the current user.
    question = body.question.strip() # .strip() removes whitespace from the beginning and end of the question.

    # If the question contains only spaces, .strip() produces an empty string.
    #  The API rejects it with HTTP 400 Bad Request.
    if not question:
        raise HTTPException(400, "Question is empty")

    try:
        return ask(db, user_id, conv, question) # calls the ask function from services/chat.py
    except Exception:
        logger.exception("Answering failed for conversation %s", conversation_id)
        db.rollback() # rolls back the current database transaction, undoing uncommitted changes in that transaction.
        raise HTTPException(
            503, "Could not generate an answer right now. Please try again."
        )


# Deletes one chat/conversation when you click the × button in the sidebar.
# @router.delete runs on a DELETE request
# means “No Content”: success, nothing to send back. That’s why the function has no return.
@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    conv = _get_conversation(db, user_id, conversation_id) # checks that the conversation exists and belongs to the current user
    db.delete(conv) # marking the chat for deletion
    db.commit() # making the deletion permanent in the database.