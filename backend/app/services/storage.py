from pathlib import Path

# imports your application's configuration settings.
# bcz we defined Which storage backend to use. Where files should be stored in that settings class
from app.core.config import settings


# This class esponsible for managing files on your local disk.
class LocalStorage:
    # Constructor gets the storage folder's full path and creates that folder if it doesn't already exist.
    def __init__(self, base_path: str): 
        # # converts the given base_path into an absolute path.
        self.base = Path(base_path).resolve()  
        # This creates the storage directory if it doesn't already exist. 
        self.base.mkdir(parents=True, exist_ok=True)  # exist_ok=True -> doesn't raise an error if the directory already exists.

    # Checks whether you are requesting files from provided folder
    # prevents from using your application to access unrelated files on your computer.
    def _safe_path(self, path: str) -> Path:
        full = (self.base / path).resolve() # We create the full file path.
        if not full.is_relative_to(self.base): # We check whether the full path is inside the storage folder.
            raise ValueError("Invalid storage path")
        return full

    # creates the required folders if they don't exist, saves the file data there, and returns the file's original path.
    def save(self, path: str, data: bytes) -> str:
        full = self._safe_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return path

    # reads the file's data from storage, and returns that data as bytes.
    def download(self, path: str) -> bytes:
        return self._safe_path(path).read_bytes()

    # safely deletes the specified file and then removes any empty parent folders, 
    # but never deletes the main storage folder.
    def delete(self, path: str) -> None:
        full = self._safe_path(path)
        full.unlink(missing_ok=True)

        # remove folders that are now empty, but never the storage root
        parent = full.parent
        while parent != self.base and parent.is_relative_to(self.base):
            try:
                parent.rmdir()  # only works when the folder is empty
            except OSError:
                break
            parent = parent.parent

# checks which storage system is configured and, 
# if it is local, creates and returns a LocalStorage object;
def get_storage():
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_path) 
    raise ValueError(f"Unknown storage backend: {settings.storage_backend}")