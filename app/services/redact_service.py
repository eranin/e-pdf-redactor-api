from app.config import STORAGE_DRIVER
from app.services.pdf_processor import redact_pdf
from app.storage.minio import MinIOStorage
from app.storage.s3 import S3Storage
from app.storage.local import LocalStorage


def get_storage():
    if STORAGE_DRIVER == "minio":
        return MinIOStorage()
    if STORAGE_DRIVER == "s3":
        return S3Storage()
    return LocalStorage()


def handle_redact(request):
    storage = get_storage()

    original_pdf = storage.download(request.source_uri)
    redacted_pdf = redact_pdf(original_pdf, request.rules)

    return storage.upload(request.source_uri, redacted_pdf)
