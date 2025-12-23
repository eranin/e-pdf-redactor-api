import os
from app.storage.base import StorageDriver
from app.config import LOCAL_STORAGE_PATH
from app.utils.uri import parse_uri


class LocalStorage(StorageDriver):
    def download(self, uri: str) -> bytes:
        info = parse_uri(uri)
        path = os.path.join(LOCAL_STORAGE_PATH, info["path"])
        with open(path, "rb") as f:
            return f.read()

    def upload(self, uri: str, content: bytes) -> str:
        info = parse_uri(uri)
        path = os.path.join(LOCAL_STORAGE_PATH, info["path"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return uri
