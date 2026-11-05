# main.py - Entry point of the backend: creates the app, sets up logging and CORS,
# registers all routers, and provides a health check endpoint.

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.core.config import settings

# Show INFO level logs and WARNINGS, ERRORS DEBUG messages etc. for the whole application
logging.basicConfig(level=logging.INFO)

# Reduce noise: only show warnings/errors from these libraries
# Libraries like httpx and google_genai shows more info logs 
# so we ignore INFO (and DEBUG) messages. only allow to show WARNINGS, ERRORS
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)

# Create the main FastAPI app (title appears in the /docs page)
app = FastAPI(title="PREPSIDE")

# CORS: allows the frontend (running on a different origin) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # which frontend URLs are allowed (from config)
    allow_methods=["*"],                  # allow all HTTP methods (GET, POST, PUT, DELETE...)
    allow_headers=["*"],                  # allow all request headers
)

# Register the routers so their endpoints become part of the app
app.include_router(documents_router)      # endpoints for documents
app.include_router(conversations_router)  # endpoints for conversations

# Health check endpoint: used to verify the server is running
@app.get("/health")
def health():
    return {"status": "ok"}