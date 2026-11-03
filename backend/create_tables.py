from app.db.session import Base, engine
from app.db import models  # noqa: F401

Base.metadata.create_all(engine)
print("tables created")