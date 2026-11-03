from pathlib import Path

from app.core.config import settings


class LocalStorage:
    def __init__(self, base_path: str):
        self.base = Path(base_path).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, path: str) -> Path:
        full = (self.base / path).resolve()
        if not full.is_relative_to(self.base):
            raise ValueError("Invalid storage path")
        return full

    def save(self, path: str, data: bytes) -> str:
        full = self._safe_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return path

    def download(self, path: str) -> bytes:
        return self._safe_path(path).read_bytes()

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


def get_storage():
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_path)
    raise ValueError(f"Unknown storage backend: {settings.storage_backend}")