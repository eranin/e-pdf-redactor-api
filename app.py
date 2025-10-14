from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import io
import json
import fitz  # PyMuPDF

# ---- App metadata (Eranin branding, author hphun9) ----
app = FastAPI(
    title="Eranin PDF Redaction API",
    description="PDF redaction service by Eranin. Fast bounding-box redaction powered by FastAPI + PyMuPDF.",
    version="1.1.0",
    license_info={
        "name": "AGPL v3",
        "url": "https://www.gnu.org/licenses/agpl-3.0.html",
    },
    contact={
        "name": "hphun9",
        "url": "https://eranin.com",
        "email": "support@eranin-tech.com",
    },
)

# ---- CORS (relax as needed) ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Models ----
class CoordinateItem(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    color: Optional[tuple] = (1, 1, 1)  # default white fill for redaction

class PageCoordinates(BaseModel):
    coordinates: List[CoordinateItem]

# ---- Optimized processing ----
def process_pdf(pdf_buffer: bytes, pages_coordinates: Dict[int, List[CoordinateItem]]) -> bytes:
    # Optimizations:
    # 1) Add all redaction rectangles per page first
    # 2) Call page.apply_redactions() once per page
    # 3) Save with garbage=3, deflate=True, clean=True for smaller/faster output
    doc = fitz.open(stream=pdf_buffer, filetype="pdf")
    try:
        for page_num, coordinates_list in pages_coordinates.items():
            if page_num < 0 or page_num >= len(doc):
                continue
            page = doc[page_num]
            for coord in coordinates_list:
                rect = fitz.Rect(float(coord.x1), float(coord.y1), float(coord.x2), float(coord.y2))
                annot = page.add_redact_annot(rect)
                annot.set_colors(stroke=coord.color, fill=coord.color)
                annot.update()
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        out = io.BytesIO()
        doc.save(out, garbage=3, deflate=True, clean=True)
        return out.getvalue()
    finally:
        doc.close()

# ---- Routes ----
@app.post("/redact-pdf", response_class=StreamingResponse)
async def redact_pdf(
    pdf_file: UploadFile = File(...),
    request_data: str = Form(...),
) -> StreamingResponse:
    try:
        pdf_content = await pdf_file.read()
        data = json.loads(request_data)
        pages_coordinates: Dict[int, List[CoordinateItem]] = {}
        for p_str, coords in data.get("pages_coordinates", {}).items():
            p_idx = int(p_str)
            pages_coordinates[p_idx] = [CoordinateItem(**c) for c in coords]
        result = process_pdf(pdf_content, pages_coordinates)
        return StreamingResponse(io.BytesIO(result), media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
