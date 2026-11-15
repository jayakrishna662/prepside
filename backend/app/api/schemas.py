# This file defines the structure of data that your API accepts and returns.
import uuid
from datetime import datetime

# BaseModel --> tells pydantic to Treat this class as a data model, and validate the data according to the rules I define.
# BaseModel gives that class Pydantic's validation and data-handling features.
# ConfigDict --> allows Pydantic to read data from an object's attributes, such as a database model's filename attribute.
# Field  --> is a function provided by Pydantic that lets you add extra rules or settings to a data field.
from pydantic import BaseModel, ConfigDict, Field


# DocumentOut describes the shape(structure) of the document data sent in the API response.
# This class defines what document information your API returns to the frontend.
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID # Unique document ID
    filename: str # Name of the uploaded document
    status: str # 	Processing status
    error_message: str | None  # Error details if processing fails
    page_count: int | None  # Number of pages in the doc
    chunks_total: int # Total chunks created from the doc
    chunks_done: int # Number of chunks processed so far
    created_at: datetime # When the document record was created
    updated_at: datetime # When the record was last updated


# CitationOut defines the information that is sent to the frontend to show where an answer came from.
class CitationOut(BaseModel):
    document_id: uuid.UUID # The unique ID of the source document
    filename: str # Filename
    page: int # The page where the relevant information was found
    has_image: bool = False # Whether the citation indicates that the page contains an image(Bydefault its False )


# MessageOut defines what information the backend sends for each chat message. Eg: answer, citations,  other details etc.
class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID # Unique ID of the message
    role: str # Who sent it, such as user or assistant
    content: str # The actual message text
    found: bool | None # Whether relevant information was found, or None if unspecified
    citations: list[CitationOut] | None # A list of sources(citations) for the answer, or None
    created_at: datetime # When the message was created

# ConversationOut defines what information the backend sends to frontend about one conversation.
class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID # Unique ID of Converstaion
    title: str # Conversation title displayed in the sidebar
    created_at: datetime # When the conversation was created
    updated_at: datetime # When the conversation was last updated

# AskIn defines the data that the backend expects when a user asks a question.
class AskIn(BaseModel):
    # The question must be string
    # Field(...): adds validation rules to that field.
    # at least one character, question cant be empty
    # it cannot exceed 1,000 characters.
    question: str = Field(min_length=1, max_length=1000)