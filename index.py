from fastapi import FastAPI, HTTPException, File, UploadFile, Form, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
import fitz, io, json, asyncio, tempfile, os
from datetime import datetime

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

class PageCoordinates(BaseModel):
    coordinates: List[CoordinateItem]

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

def find_text_coordinates(words: List, text_to_find: str, bound_x1: float, bound_x2: float,
                         bound_y1: float, bound_y2: float) -> Optional[tuple]:
    """Find coordinates of specific text within the specified bounds"""
    # Split text_to_find into individual words and clean them
    search_words = [word.lower().strip() for word in text_to_find.split()]
    for word in words:
        word_x1, word_y1, word_x2, word_y2 = word[:4]
        if (bound_x1 <= word_x1 <= bound_x2 or bound_x1 <= word_x2 <= bound_x2) and \
           (bound_y1 <= word_y1 <= bound_y2 or bound_y1 <= word_y2 <= bound_y2):
            if text_to_find.lower().strip() in word[4].lower().strip():
                return (word_x1, word_y1, word_x2, word_y2)
            if search_words[0].lower().strip() in word[4].lower().strip():
                return (word_x1, word_y1, word_x2, word_y2)
    return None

def get_bounded_line_coordinates(text_y1: float, text_y2: float,
                               bound_x1: float, bound_x2: float) -> tuple:
    """Get coordinates for the line containing the text, bounded by the specified area"""
    return (bound_x1, text_y1, bound_x2, text_y2)

def get_bounded_column_coordinates(text_x1: float, text_x2: float,
                                 bound_y1: float, bound_y2: float) -> tuple:
    """Get coordinates for the column containing the text, bounded by the specified area"""
    return (text_x1, bound_y1, text_x2, bound_y2)

def is_rectangle_inside(
    xa1: float, ya1: float, xa2: float, ya2: float,  # Tọa độ hình chữ nhật A (bên ngoài)
    xb1: float, yb1: float, xb2: float, yb2: float   # Tọa độ hình chữ nhật B (bên trong)
) -> bool:
    """
    Kiểm tra xem hình chữ nhật B có nằm hoàn toàn trong hình chữ nhật A không
    Args:
        xa1, ya1: Tọa độ điểm đầu của hình chữ nhật A
        xa2, ya2: Tọa độ điểm cuối của hình chữ nhật A
        xb1, yb1: Tọa độ điểm đầu của hình chữ nhật B
        xb2, yb2: Tọa độ điểm cuối của hình chữ nhật B
    Returns:
        bool: True nếu B nằm hoàn toàn trong A, False nếu không
    """
    # Xác định các cạnh của hình chữ nhật A
    x_min_a = min(xa1, xa2)
    x_max_a = max(xa1, xa2)
    y_min_a = min(ya1, ya2)
    y_max_a = max(ya1, ya2)
    # Xác định các cạnh của hình chữ nhật B
    x_min_b = min(xb1, xb2)
    x_max_b = max(xb1, xb2)
    y_min_b = min(yb1, yb2)
    y_max_b = max(yb1, yb2)
    # Kiểm tra xem B có nằm hoàn toàn trong A không
    return (x_min_a <= x_min_b and x_max_b <= x_max_a and
            y_min_a <= y_min_b and y_max_b <= y_max_a)

def is_point_in_rectangle(
   rect_x1: float, rect_y1: float, rect_x2: float, rect_y2: float,  # Tọa độ hình chữ nhật
   point_x: float, point_y: float  # Tọa độ điểm cần kiểm tra
) -> bool:
   # Xác định các cạnh của hình chữ nhật
   x_min = min(rect_x1, rect_x2)
   x_max = max(rect_x1, rect_x2)
   y_min = min(rect_y1, rect_y2)
   y_max = max(rect_y1, rect_y2)
   # Kiểm tra điểm có nằm trong khoảng x và y không
   return (x_min <= point_x <= x_max and y_min <= point_y <= y_max)

# ─────────────────────────────
# ⚡ Fast redaction (in-memory)
# ─────────────────────────────
def process_pdf_basic(pdf_buffer: bytes, pages_coordinates: Dict[int, List[CoordinateItem]]) -> bytes:
    """Original PDF processing function"""
    doc = fitz.open(stream=pdf_buffer, filetype="pdf")
    try:
        for page_num, coordinates_list in pages_coordinates.items():
            if page_num >= len(doc):
                print(f"Bỏ qua trang {page_num}: Số trang không hợp lệ. PDF chỉ có {len(doc)} trang.")
                continue
            page = doc[page_num]
            words = page.get_text("words")
            for coord in coordinates_list:
                x1, y1 = coord.x1, coord.y1
                x2, y2 = coord.x2, coord.y2
                color = (1, 0, 0)
                for word in words:
                    word_x1, word_y1, word_x2, word_y2 = word[:4]
                    if (x1 <= word_x1 <= x2 or x1 <= word_x2 <= x2) and \
                       (y1 <= word_y1 <= y2 or y1 <= word_y2 <= y2):
                        rect = fitz.Rect(word_x1, word_y1, word_x2, word_y2)
                        annot = page.add_redact_annot(rect)
                        # annot.set_colors(stroke=color, fill=color)
                        annot.update()
                        page.apply_redactions()
                # rect = fitz.Rect(x1, y1, x2, y2)
                shape = page.new_shape()
                # shape.draw_rect(rect)
                # shape.finish(fill=(1, 0, 0), color=(1, 0, 0))
                shape.commit()
        output_buffer = io.BytesIO()
        doc.save(output_buffer)
        return output_buffer.getvalue()
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

def process_pdf_advanced(pdf_buffer: bytes, rules: List[Rule]) -> bytes:
    """Advanced PDF processing function with pattern-based redaction"""
    doc = fitz.open(stream=pdf_buffer, filetype="pdf")
    try:
        for rule in rules:
            if rule.pageNumber - 1 >= len(doc):
                print(f"Bỏ qua trang {rule.pageNumber}: Số trang không hợp lệ. PDF chỉ có {len(doc)} trang.")
                continue
            page = doc[rule.pageNumber - 1]
            words = page.get_text("words")
            bound_x1, bound_y1, bound_x2, bound_y2 = convert_coordinates(rule.coordinates.dict())
            x1, y1, x2, y2 = bound_x1, bound_y1, bound_x2, bound_y2
            # print(x1, y1, x2, y2)
            if rule.text_find:
                text_coords = find_text_coordinates(
                    words,
                    rule.text_find,
                    bound_x1,
                    bound_x2,
                    bound_y1,
                    bound_y2
                )
                if text_coords:
                    if rule.patternType == "full-line":
                        x1, y1, x2, y2 = get_bounded_line_coordinates(
                            text_coords[1],
                            text_coords[3],
                            bound_x1,
                            bound_x2
                        )
                    elif rule.patternType == "full-column":
                        x1, y1, x2, y2 = get_bounded_column_coordinates(
                            text_coords[0],
                            text_coords[2],
                            bound_y1,
                            bound_y2
                        )
            space = 2
            print(rule)
            if rule.ruleType != "all-text":
                space = 40
            for word in words:
                word_x1, word_y1, word_x2, word_y2 = word[:4]
                # if (is_rectangle_inside(x1 - 5, y1 - 5, x2 + 5, y2 + 5, word_x1, word_y1, word_x2, word_y2)):
                if (is_point_in_rectangle(x1 + space, y1 - 1, x2 + 2, y2 + 1, word_x1, word_y1)):
                #    (y1 <= word_y1 <= y2 or y1 <= word_y2 <= y2):
                    rect = fitz.Rect(word_x1, word_y1, word_x2, word_y2)
                    annot = page.add_redact_annot(rect)
                    # annot.set_colors(stroke=(1, 1, 1), fill=(1, 1, 1))
                    annot.update()
                    page.apply_redactions()
            rect = fitz.Rect(word_x1, word_y1, word_x2, word_y2)
            shape = page.new_shape()
            # shape.draw_rect(rect)
            # shape.finish(fill=(1, 1, 1), color=(1, 1, 1))
            shape.commit()
        output_buffer = io.BytesIO()
        doc.save(output_buffer)
        return output_buffer.getvalue()
    finally:
        doc.close()

# ─────────────────────────────
# 🚀 Routes
# ─────────────────────────────
@app.post("/redact-pdf-advanced")
async def redact_pdf_advanced(
    file: UploadFile = File(...),
    request: str = Form(...)  # Thay đổi từ Body(...) thành Form(...)
):
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Chỉ chấp nhận file PDF"
            )
        # Read file content
        pdf_content = await file.read()
        if not pdf_content:
            raise HTTPException(
                status_code=400,
                detail="File PDF rỗng"
            )
        # Parse JSON request string
        try:
            request_data = json.loads(request)
            request_obj = RedactPDFRequest(**request_data)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Lỗi parse JSON: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Lỗi validate request data: {str(e)}"
            )
        # Process PDF with rules
        try:
            result = process_pdf_advanced(pdf_content, request_obj.rules)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi xử lý PDF: {str(e)}"
            )
        # Create filename for processed PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"redacted_{timestamp}_{file.filename}"
        # Return processed PDF as StreamingResponse
        return StreamingResponse(
            io.BytesIO(result),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{file.filename}"'
            }
        )
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi không xác định: {str(e)}"
        )

@app.post("/redact-pdf")
async def redact_pdf(
    pdf_file: UploadFile = File(...),
    request_data: str = Form(...)
) -> StreamingResponse:
    try:
        pdf_content = await pdf_file.read()
        request_data = request_data.encode('utf-8')
        request = json.loads(request_data)
        pages_coordinates = {}
        for page_num, coords in request['pages_coordinates'].items():
            page_num = int(page_num)
            pages_coordinates[page_num] = [CoordinateItem(**coord) for coord in coords]
        result_buffer = process_pdf_basic(pdf_content, pages_coordinates)
        return StreamingResponse(io.BytesIO(result_buffer), media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
