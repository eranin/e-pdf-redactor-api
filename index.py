from fastapi import FastAPI, HTTPException, File, UploadFile, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import fitz, io, json, asyncio, tempfile, os

# ─────────────────────────────
# ⚙️ App Info (Eranin Metadata)
# ─────────────────────────────
app = FastAPI(
    title="Eranin PDF Redaction API",
    description="Fast bounding-box redaction service for PDFs, developed by Eranin using FastAPI + PyMuPDF.",
    version="1.1.0",
    license_info={"name": "AGPL v3", "url": "https://www.gnu.org/licenses/agpl-3.0.html"},
    contact={"name": "hphun9", "url": "https://eranin.com", "email": "support@eranin-tech.com"}
)

# ─────────────────────────────
# 🌐 CORS setup (allow internal + FE)
# ─────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or list of allowed domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────
# 📦 Model definitions
# ─────────────────────────────
class CoordinateItem(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    color: Optional[tuple] = (1, 0, 0)  # Default red

class Coordinates(BaseModel):
    x: float
    y: float
    width: float
    height: float

class Rule(BaseModel):
    fieldName: str
    ruleType: str
    coordinates: Coordinates
    pageNumber: int = Field(ge=0)
    patternType: Optional[str] = None
    text_find: Optional[str] = None

class RedactPDFRequest(BaseModel):
    rules: List[Rule]

# ─────────────────────────────
# 🧠 Concurrency limiter
# Prevents server crash when 400 files come at once
# ─────────────────────────────
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "6"))
_sema = asyncio.Semaphore(MAX_CONCURRENCY)

# ─────────────────────────────
# 🔧 Utility functions
# ─────────────────────────────
def convert_coordinates(coord: Dict[str, float]) -> tuple:
    """Convert coordinates from JSON format to PDF coordinates"""
    return (
        coord['x']//2,
        coord['y']//2,
        coord['x']//2 + coord['width']//2,
        coord['y']//2 + coord['height']//2
    )

def is_point_in_rectangle(rx1, ry1, rx2, ry2, px, py) -> bool:
    """Check if a point lies within a rectangle"""
    return (min(rx1, rx2) <= px <= max(rx1, rx2)
            and min(ry1, ry2) <= py <= max(ry1, ry2))

# ─────────────────────────────
# ⚡ Fast redaction (in-memory)
# ─────────────────────────────
def process_pdf_basic(pdf_buffer: bytes, pages_coordinates: Dict[int, List[CoordinateItem]]) -> bytes:
    """
    Faster redaction method using PyMuPDF.
    Works in-memory, suitable for small/medium PDFs.
    """
    doc = fitz.open(stream=pdf_buffer, filetype="pdf")
    try:
        for page_num, coords_list in pages_coordinates.items():
            if page_num >= len(doc): 
                continue
            page = doc[page_num]
            for coord in coords_list:
                rect = fitz.Rect(coord.x1, coord.y1, coord.x2, coord.y2)
                annot = page.add_redact_annot(rect)
                annot.update()
            page.apply_redactions()
        buf = io.BytesIO()
        doc.save(buf, garbage=3, deflate=True, clean=True)
        return buf.getvalue()
    finally:
        doc.close()

# ─────────────────────────────
# 🧱 Disk-based redaction (low RAM)
# ─────────────────────────────
def process_pdf_basic_to_file(pdf_buffer: bytes, pages_coordinates: Dict[int, List[CoordinateItem]]) -> str:
    """
    Lower-memory version — writes to disk instead of holding entire buffer in RAM.
    Use when many concurrent requests are expected.
    """
    doc = fitz.open(stream=pdf_buffer, filetype="pdf")
    try:
        for page_num, coords_list in pages_coordinates.items():
            if page_num >= len(doc): 
                continue
            page = doc[page_num]
            for coord in coords_list:
                rect = fitz.Rect(coord.x1, coord.y1, coord.x2, coord.y2)
                annot = page.add_redact_annot(rect)
                annot.update()
            page.apply_redactions()

        fd, out_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        doc.save(out_path, garbage=3, deflate=True, clean=True)
        return out_path
    finally:
        doc.close()

def _cleanup(path: str):
    """Delete temp file after response is sent"""
    try:
        os.remove(path)
    except:
        pass

# ─────────────────────────────
# 🚀 Routes
# ─────────────────────────────
@app.post("/redact-pdf")
async def redact_pdf(background: BackgroundTasks, pdf_file: UploadFile = File(...), request_data: str = Form(...)):
    """
    Redact PDF with bounding box coordinates.
    Automatically throttled with concurrency semaphore.
    Uses disk-based mode to reduce memory pressure.
    """
    async with _sema:
        pdf_content = await pdf_file.read()
        data = json.loads(request_data)
        pages_coords = {int(k): [CoordinateItem(**v) for v in lst] for k, lst in data["pages_coordinates"].items()}
        out_path = process_pdf_basic_to_file(pdf_content, pages_coords)
        background.add_task(_cleanup, out_path)
        return FileResponse(out_path, media_type="application/pdf", filename="redacted.pdf")

@app.get("/")
async def root():
    """Simple homepage"""
    return FileResponse("index.html")

@app.get("/healthz")
async def healthz():
    """Health check endpoint"""
    return {"status": "ok"}

# ─────────────────────────────
# 🧩 Local run (for debugging)
# ─────────────────────────────
if __name__ == "__main__":
    import uvicorn
    # Run single worker to avoid duplicate memory usage
    uvicorn.run("index:app", host="0.0.0.0", port=3000, reload=True)
