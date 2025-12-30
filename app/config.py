import os

STORAGE_DRIVER = os.getenv("STORAGE_DRIVER", "minio")

# MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "storage.eranin.com")
MINIO_PORT = os.getenv("MINIO_PORT", "443")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "Np2gi4aaWwFspwly")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "wucrXoZE5sDOsUMIXqW9zfg1dOw3ID4W")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "asmara-chubbies-tool1")

# AWS S3
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

# Local storage
LOCAL_STORAGE_PATH = os.getenv("LOCAL_STORAGE_PATH", "/tmp/pdf-storage")
