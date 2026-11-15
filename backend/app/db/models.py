# models.py defines the database tables as python class.

# uuid is a Python module used to generate unique identifiers.
# In this project, UUIDs identify documents, chunks, conversations, and messages.
import uuid

# 	Date and time values (like created_at)
from datetime import datetime

# import vector that stores embeddings
from pgvector.sqlalchemy import Vector

# import Column types from sqlalchemy
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,  # Prevents duplicate combinations of values in specified columns.
    func,  # Allows you to use SQL database functions through SQLAlchemy.
)

# UUID is a SQLAlchemy type used to define UUID columns in PostgreSQL.
# JSONB lets PostgreSQL store structured JSON data in a database column.
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Mapped indicates the type of the value(in python)
# mapped_column indicates the details of the column(in database)
from sqlalchemy.orm import Mapped, mapped_column

# Base is the common parent that tells SQLAlchemy which classes are tables.”
from app.db.session import Base


# defines the structure of documents table.
class Document(Base):
    __tablename__ = "documents" # 	The real table name in PostgreSQL
    __table_args__ = (UniqueConstraint("user_id", "file_hash"),) # The same user can’t have the same file twice.

    # column = id, stores the UUID of document, this column is primary key
    # Automatically generates a UUID for a new document
    # python UUID type is mapped with postgres UUID column type
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # column = user_id , stores the UUID of the user who uploaded the document.
    # index=True means create database index for this column to find matching records more efficiently
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    # column = filename , Stores the name of the uploaded file.
    # stores upto 255 characters in db
    filename: Mapped[str] = mapped_column(String(255))

    # column = storage_path, Stores the location where the uploaded file is saved.
    storage_path: Mapped[str] = mapped_column(String(500))

    # column = file_hash, file hash is a value calculated from a file's contents using a hashing algorithm.
    # To detect duplicate uploads and skip re-processing the same PDF, which saves embedding calls.”
    file_hash: Mapped[str] = mapped_column(String(64))

    # column = file_size , used for Used for checking the upload limit    
    file_size: Mapped[int] = mapped_column(BigInteger)

    # column = page_count, Number of pages in the file.
    # This value can be int or None , bcz When a user uploads a file, 
    # your application might not have calculated its page count yet.
    # it’s filled in later, during the “Reading file” step.
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # column = status ,It stores the current processing state of an uploaded file.
    # It starts as "uploaded" (the default), then the backend updates it as it moves along next process.
    status: Mapped[str] = mapped_column(String(20), default="uploaded")

    # column = error_message, stores details about an error if something goes wrong while processing a file
    # the frontend shows this text in red under the filename.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # column = chunks_total , stores the total number of chunks created from that file
    chunks_total: Mapped[int] = mapped_column(Integer, default=0)

    # column = chunks_done , It stores how many chunks have been processed so far.
    # it grows as chunks are processed.
    chunks_done: Mapped[int] = mapped_column(Integer, default=0)

    # column = created_at, It stores the date and time when the document record was created in the database.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # column = updated_at , stores the date and time when it was last updated.
    # Every time the row is updated (like status changing), updated_at is set to the current time again
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )



# defines the structure of chunks table.
class Chunk(Base):
    __tablename__ = "chunks"  # Database table name

    # Unique UUID for each chunk, primary key for this table
    # generated automatically
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # This is foreign key ,References the parent document; deleting it also deletes its chunks
    # created index for this column , bcz we need to find chunks using document_id quickly.
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )

    # ID of the user who owns this chunk; index speeds up user-based queries
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    # Position of this particular chunk within the document's chunks
    chunk_index: Mapped[int] = mapped_column(Integer)

    # page number from which this particular chunk was extracted
    page: Mapped[int] = mapped_column(Integer)

    # Actual text content of the chunk
    content: Mapped[str] = mapped_column(Text)

    # Type of chunk; defaults to "text"
    # we have text,and image types
    # text for -> The chunk contains extracted text from a file.
    # image for -> 	The chunk that represents image-related content.
    kind: Mapped[str] = mapped_column(String(20), default="text", server_default="text")

    # It stores the file path of an associated asset, such as an extracted image.
    # Imagine your PDF contains a diagram. Your application extracts that diagram and saves it as a separate image file.
    # now that chunk is linked to that image.
    asset_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # embeddings of the chunk , stored as a list of 1536 numbers.
    # Why 1536? It’s the size of the our embedding model’s output.
    embedding = mapped_column(Vector(1536))

    # stores date and time of when this chunk created
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# defines the structure of conversations table.
class Conversation(Base):
    __tablename__ = "conversations" # Database table name

    # Unique UUID for each conversation, generated automatically
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ID of the user who owns the conversation; index speeds up user-based queries
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    # Conversation title; defaults to "New chat"
    title: Mapped[str] = mapped_column(String(200), default="New chat")

    # Timestamp when the conversation is created
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Timestamp when the conversation is updated
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

# defines the structure of Message table.
class Message(Base):
    __tablename__ = "messages" # Database table name

    # Unique UUID for each message, generated automatically
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # References the conversation this message belongs to
    # Deleting the conversation also deletes its messages
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )

    # Identifies who sent the message: "user" or "assistant"
    role: Mapped[str] = mapped_column(String(20)) 

    # Stores the actual message text
    content: Mapped[str] = mapped_column(Text)

    #  True/False value indicating whether relevant information was found
    found: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    #  JSON data storing citations or source references
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Timestamp when the message record is created
    # func.clock_timestamp() gives the real current time, unlike now() which is fixed at the start of the transaction. 
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )