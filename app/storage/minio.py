from minio import Minio
from io import BytesIO
from app.storage.base import StorageDriver
from app.config import *
from app.utils.uri import parse_uri


class MinIOStorage(StorageDriver):
    def __init__(self):
        # Combine endpoint and port if port is specified
        endpoint = f"{MINIO_ENDPOINT}:{MINIO_PORT}" if MINIO_PORT else MINIO_ENDPOINT
        self.client = Minio(
            endpoint,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        self.bucket_name = MINIO_BUCKET_NAME

    def download(self, uri: str) -> bytes:
        info = parse_uri(uri)
        obj = self.client.get_object(self.bucket_name, info["path"])
        return obj.read()

    def upload(self, uri: str, content: bytes) -> str:
        info = parse_uri(uri)
        self.client.put_object(
            self.bucket_name,
            info["path"],
            BytesIO(content),
            length=len(content),
            content_type="application/pdf"
        )
        return uri
