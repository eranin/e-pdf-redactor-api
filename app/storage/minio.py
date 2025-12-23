from minio import Minio
from io import BytesIO
from app.storage.base import StorageDriver
from app.config import *
from app.utils.uri import parse_uri


class MinIOStorage(StorageDriver):
    def __init__(self):
        self.client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )

    def download(self, uri: str) -> bytes:
        info = parse_uri(uri)
        obj = self.client.get_object(info["bucket"], info["path"])
        return obj.read()

    def upload(self, uri: str, content: bytes) -> str:
        info = parse_uri(uri)
        self.client.put_object(
            info["bucket"],
            info["path"],
            BytesIO(content),
            length=len(content),
            content_type="application/pdf"
        )
        return uri
