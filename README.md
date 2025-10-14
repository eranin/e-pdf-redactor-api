
<p align="center">
  <img src="logo.png" alt="Eranin Logo" width="120"/>
</p>

# Eranin PDF Redaction API (Author: hphun9)
Fast bounding-box redaction for PDFs (FastAPI + PyMuPDF).

## Quick Start

```bash
# Create Venv
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
uvicorn index:app --reload --port 3000

```

### Request Example

```bash
curl -X POST http://localhost:8000/redact-pdf \
  -F "pdf_file=@/path/to/input.pdf" \
  -F 'request_data={
    "pages_coordinates": {
      "0": [{"x1": 50, "y1": 50, "x2": 200, "y2": 100}],
      "1": [{"x1": 100, "y1": 120, "x2": 240, "y2": 180}]
    }
  }'
```

## License (AGPL v3)

This repository is distributed under the **GNU Affero General Public License v3**.

- Copyright (C) 2025  Original author(s)
- Modifications Copyright (C) 2025  hphun9 (Eranin)

Per AGPL requirements, source changes must be shared under the same license.
