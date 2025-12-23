from urllib.parse import urlparse


def parse_uri(uri: str):
    """
    Example:
    minio://bucket/path/file.pdf
    s3://bucket/path/file.pdf
    """
    parsed = urlparse(uri)
    return {
        "scheme": parsed.scheme,
        "bucket": parsed.netloc,
        "path": parsed.path.lstrip("/")
    }
