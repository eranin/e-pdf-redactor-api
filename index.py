from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional
import fitz
import io
import json
from fastapi.responses import FileResponse

app = FastAPI(
    title="My Application",
    description="This application uses libraries licensed under the AGPL.",
    version="1.0.0",
    license_info={
        "name": "AGPL v3",
        "url": "https://www.gnu.org/licenses/agpl-3.0.html"
    },
    contact={
        "name": "py-redact-redaction-api",
        "url": "https://github.com/Toanf2103/py-redact-redaction-api",  # Thay link GitHub của bạn
        "email": "nobitakute002@gmail.com"
    }
)

# Để phục vụ các tệp tĩnh (chẳng hạn như CSS hoặc hình ảnh) nếu cần
# app.mount("/", StaticFiles(directory="static"), name="static")

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả các domain, hoặc bạn có thể giới hạn như ["http://localhost:3000"]
    allow_credentials=True,  # Cho phép gửi cookie hoặc thông tin xác thực qua request
    allow_methods=["*"],  # Cho phép tất cả các HTTP methods (GET, POST, PUT, DELETE, ...)
    allow_headers=["*"],  # Cho phép tất cả các headers (Content-Type, Authorization, ...)
)

class CoordinateItem(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    color: Optional[tuple] = (1, 0, 0)

class PageCoordinates(BaseModel):
    coordinates: List[CoordinateItem]

def process_pdf(pdf_buffer: bytes, pages_coordinates: Dict[int, List[CoordinateItem]]) -> bytes:
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
                # color = coord.color if hasattr(coord, 'color') else (1, 0, 0)
                color = (1, 1, 1)

                for word in words:
                    word_x1, word_y1, word_x2, word_y2 = word[:4]

                    if (x1 <= word_x1 <= x2 or x1 <= word_x2 <= x2) and \
                       (y1 <= word_y1 <= y2 or y1 <= word_y2 <= y2):
                        rect = fitz.Rect(word_x1, word_y1, word_x2, word_y2)
                        annot = page.add_redact_annot(rect)
                        annot.set_colors(stroke=color, fill=color)
                        annot.update()
                        page.apply_redactions()
                        
                # Thêm rectangle màu trắng phủ toàn bộ vùng
                rect = fitz.Rect(x1, y1, x2, y2)
                shape = page.new_shape()
                shape.draw_rect(rect)
                shape.finish(fill=(1, 1, 1), color=(1, 1, 1))  # fill và stroke đều màu trắng
                shape.commit()

        output_buffer = io.BytesIO()
        doc.save(output_buffer)
        return output_buffer.getvalue()

    finally:
        doc.close()

@app.post("/redact-pdf")
async def redact_pdf(
    pdf_file: UploadFile = File(...),
    request_data: str = Form(...)
)-> StreamingResponse:
    try:
        pdf_content = await pdf_file.read()
        request_data = request_data.encode('utf-8')
        request = json.loads(request_data)
        pages_coordinates = {}
        for page_num, coords in request['pages_coordinates'].items():
            page_num = int(page_num)
            pages_coordinates[page_num] = [CoordinateItem(**coord) for coord in coords]

        result_buffer = process_pdf(pdf_content, pages_coordinates)
        return StreamingResponse(io.BytesIO(result_buffer), media_type="application/pdf")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return FileResponse("index.html")

if __name__ == "main":
    import uvicorn
    # Sửa địa chỉ host từ "0.0000" thành "localhost" hoặc "0.0.0.0"
    uvicorn.run(app, host="localhost", port=3000)