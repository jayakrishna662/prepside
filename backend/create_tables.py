# creates the database tables defined in your SQLAlchemy models if they don't already exist.

# noqaF401 tells the Python linter to ignore the unused import warning on that line.
# Even though we don't use models directly, importing it registers your SQLAlchemy model classes with Base.metadata.
# If you remove it, Base.metadata.create_all(engine) might not create your tables
# because SQLAlchemy may not know about those models.
from app.db import models  # noqa: F401
from app.db.session import Base, engine

Base.metadata.create_all(engine)
print("tables created")