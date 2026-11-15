# It’s the file that connects your Python code to the database. 
# Without it, every file would set up its own connection with its own password handling and configuration.
# With it, the connection is set up once in one place, and closing is automatic.

# creat_engine --> used to create a SQLAlchemy engine that manages database connectivity 
# between our Python application and the database.
from sqlalchemy import create_engine

# DeclarativeBase --> Provides the base class for defining your database models.
# sessionmaker  --> Creates a factory for producing database sessions.
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# import settings class from config.py that holds all the configuration values
from app.core.config import settings

# engine is connection manager
# it knows where the db is, how to talk to it, and keeps a few ready connections to reuse
# Opening a new connection to the database is slow, like starting a phone call each time. 
# The engine opens a few connections in advance (called a pool), and hands one out when needed.
# pool_pre_ping=True --> checks whether a pooled database connection is alive before using it.
# bcz some of the connections may disconnects , but they still exists in pool and they no longer work.
engine = create_engine(settings.database_url, pool_pre_ping=True)


# sessionmaker creates a factory for database sessions.
# bind connects the session factory to a specific engine.
# When you make changes using a database session, 
# SQLAlchemy can send those changes to the database before you commit the transaction. This is called flush
# autoflush=False prevents SQLAlchemy from automatically flushing pending changes
SessionLocal = sessionmaker(bind=engine, autoflush=False)


# Base serves as the common parent for all our database models.
#  Other models inherit from this class so SQLAlchemy can manage their table definitions.
# DeclarativeBase class is isn't intended to be used directly for each model. First we need to create base class and then inherit from base class
# So we cant do Users(DeclarativeBase)
class Base(DeclarativeBase):
    pass


# provide a database session whenever your FastAPI endpoint needs one.
def get_db():
    # This line creates a new database session and stores it in the variable db.
    db = SessionLocal()
    try:
        # return db would return the session and finish the function immediately.
        # yield db gives the session to FastAPI while pausing the function, allowing FastAPI to resume it later and execute db.close().
        yield db
    finally:
        # closes the session and releases its resources , including gives back its connection to the connection pool.
        db.close()