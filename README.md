# PDF Redact Service

A production-ready PDF redaction service built with **FastAPI + PyMuPDF**, supporting
multiple storage backends (**Local / MinIO / AWS S3**) via environment configuration.

---

## Features

- Redact PDF by **page + bounding box (x, y, width, height)**
- Input file via **URI** (local://, minio://, s3://)
- Redacted file is uploaded back to the same storage & path
- Storage backend selected via environment variables
- Clean architecture, easy to extend

---

## Run with Docker

### Build image

```bash
docker build -t pdf-redact-service .
```

### Run container (local storage)

```bash
docker run -d \
  -p 3000:3000 \
  -e STORAGE_DRIVER=local \
  -e LOCAL_STORAGE_PATH=/data \
  -v /tmp/pdf-storage:/data \
  --name pdf-redact \
  pdf-redact-service
```

---

## API

### POST /redact

```json
{
  "source_uri": "local://docs/sample.pdf",
  "rules": [
    {
      "page": 0,
      "area": {
        "x": 100,
        "y": 150,
        "width": 200,
        "height": 40
      }
    }
  ]
}
```

### Response

```json
{
  "status": "success",
  "redacted_uri": "local://docs/sample.pdf"
}
```

---

## Notes

- PDF coordinate system is used
- Redaction is applied **in-place**
- Buckets / folders must exist before use

---

Internal usage – free to adapt.
