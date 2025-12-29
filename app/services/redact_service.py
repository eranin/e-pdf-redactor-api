from app.config import STORAGE_DRIVER
from app.services.pdf_processor import redact_pdf
from app.storage.minio import MinIOStorage
from app.storage.s3 import S3Storage
from app.storage.local import LocalStorage


def get_storage():
    print(f"[DEBUG] STORAGE_DRIVER is set to: '{STORAGE_DRIVER}'")
    if STORAGE_DRIVER == "minio":
        print("[DEBUG] Using MinIO storage")
        return MinIOStorage()
    if STORAGE_DRIVER == "s3":
        print("[DEBUG] Using S3 storage")
        return S3Storage()
    print("[DEBUG] Using Local storage (default)")
    return LocalStorage()


def handle_redact_pdf(request):
    storage = get_storage()
    try:
        original_pdf = storage.download(request.source_uri)
    except Exception as e:
        raise e
    try:
        redacted_pdf = redact_pdf(original_pdf, request.rules)
    except Exception as e:
        raise e
    from app.utils.uri import parse_uri
    info = parse_uri(request.source_uri)
    result_path = f"pdf_redacted/redacted_{info['path'].split('/')[-1]}"
    result_uri = f"{info['scheme']}://{info['bucket']}/{result_path}"
    try:
        uploaded_uri = storage.upload(result_uri, redacted_pdf)
        return uploaded_uri
    except Exception as e:
        raise e
