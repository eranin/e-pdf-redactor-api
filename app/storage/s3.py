import boto3
from io import BytesIO
from app.storage.base import StorageDriver
from app.config import *
from app.utils.uri import parse_uri


class S3Storage(StorageDriver):
    def __init__(self):
        self.client = boto3.client(
            "s3",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

    def download(self, uri: str) -> bytes:
        info = parse_uri(uri)
        obj = self.client.get_object(Bucket=info["bucket"], Key=info["path"])
        return obj["Body"].read()

    def upload(self, uri: str, content: bytes) -> str:
        info = parse_uri(uri)
        self.client.put_object(
            Bucket=info["bucket"],
            Key=info["path"],
            Body=content,
            ContentType="application/pdf"
        )
        return uri
