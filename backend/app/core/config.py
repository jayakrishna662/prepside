# config.py reads settings from .env 
# so other parts of the backend can access them without repeatedly reading the .env file.

# Path is a class from pathlib module. It helps us work with file and folder paths.
from pathlib import Path

#BaseSettings --> A class used to load application settings from environment variables or a .env file and validate their values.
# Without BaseSettings  you’d write the code to read .env, convert types and check missing values yourself.
# SettingsConfigDict --> Used to configure how BaseSettings loads its settings.
from pydantic_settings import BaseSettings, SettingsConfigDict

# importing A helper class that builds a database connection address safely.
from sqlalchemy.engine import URL

# It finds the location of your project's .env file.
# __file__ means the path of the current Python file, which is config.py.
# .resolve() gets its absolute path.
# .parents[3] moves up four directory levels from the file's directory.
# / ".env" adds the .env filename to that directory path.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


# A class that holds all the configuration values of your backend in one place.
class Settings(BaseSettings):
    google_api_key: str

    db_host: str = "localhost" # localhost is default 
    db_port: int = 5432 # 5432 is default
    db_name: str
    db_user: str
    db_password: str

    # These control where uploaded PDFs are stored.
    storage_backend: str = "local"  # Storage method -> tells which kind of storage to use. defaultly local(other options like s3, Save in cloud storage if you implement it)
    storage_path: str = "./storage" # tells Which folder to use when storage is local. ./storage means a folder named storage, Your uploaded docs go into it.
    max_upload_mb: int = 50 # upload limit 50MB

    # RAG retrieval settings
    relevance_threshold: float = 0.55  # The minimum “match score” a chunk needs to count as related.
    retrieval_top_k: int = 8  # How many chunks to fetch.

    #  When a question needs a whole named document (like “summarize Unit 1.pdf”) 
    # and that document has 40 chunks or fewer, the backend sends all its chunks to the AI.
    # if the question doesn’t need a whole document, or the document has more than 40 chunks. 
    # The normal search picks the top 8 most related chunks and keeps only those with a score of 0.55 or higher.
    whole_document_max_chunks: int = 40 


    # the maximum images sent to the AI
    max_images_per_question: int = 2

    # Decides how many top-ranked chunks are checked for page images.
    # Why: Some answers need a picture (a diagram or a figure from the PDF). The backend looks for images on the pages of the best chunks.
    # How: Only the top 3 ranked chunks are checked for images
    image_rank_window: int = 3

    # The list of frontend addresses that are allowed to call your backend.
    cors_origins: list[str] = ["http://localhost:5173"]

    # This configures the Settings class: load setting values from the .env file at ENV_FILE,
    #  and ignore extra .env entries that are not declared as settings
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")


  # It builds the database connection URL using your PostgreSQL settings.
    @property  # It allows you to access the method like an attribute, without parentheses. ( eg : settings.database_url )
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


# This creates an instance of the Settings class
# Other parts of your backend can then import and use this shared instance rather than creating a new one each time.
settings = Settings()