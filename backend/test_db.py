# i) Create a new project in supabase with name prepside 
# ii) Go to sql editor and run: CREATE EXTENSION IF NOT EXISTS vector;
#       This will create a new extension in the database and it Switch on the add-on that 
#       lets your database store embeddings and search them by similarity.
# iii) Paste your credentials from supabse into .env and then run this file to test whether your code reaches supabase
#      You should see [('vector',)]. It means your code reached Supabase and sees pgvector.

from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.database_url)

with engine.connect() as conn:
    result = conn.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    )
    print(result.fetchall())