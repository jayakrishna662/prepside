from fastapi import FastAPI

# Create the FastAPI application instance
app = FastAPI()


@app.get("/health")
def health():
    # Simple liveness check for the API
    return {"status": "ok"}
