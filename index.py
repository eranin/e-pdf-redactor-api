from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse, FileResponse
from typing import Dict, List, Optional, Union
import fitz
import io
import json
from datetime import datetime

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
        "url": "https://github.com/Toanf2103/py-redact-redaction-api",
        "email": "nobitakute002@gmail.com"
    }
)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models cho phương thức redact-pdf cũ
class CoordinateItem(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    color: Optional[tuple] = (1, 0, 0)

class PageCoordinates(BaseModel):
    coordinates: List[CoordinateItem]

# Models cho phương thức redact-pdf-advanced
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

def convert_coordinates(coord: Dict[str, float]) -> tuple:
    """Convert coordinates from x,y,width,height format to x1,y1,x2,y2 format"""
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

def process_pdf_advanced_template(pdf_buffer: bytes, rules: List[Rule]) -> bytes:
    """Advanced PDF processing function with pattern-based redaction"""
    doc = fitz.open(stream=pdf_buffer, filetype="pdf")

    try:
        for rule in rules:
            # Validate page
            if rule.pageNumber - 1 >= len(doc):
                continue

            page = doc[rule.pageNumber - 1]
            words = page.get_text("words")

            bound_x1, bound_y1, bound_x2, bound_y2 = convert_coordinates(rule.coordinates.dict())

            # 1) TABLE / HAVE-VALUE: specialized column redaction using header detection and row grouping
            if rule.ruleType in ("table", "have-value") and rule.text_find:
                tb_x1, tb_y1, tb_x2, tb_y2 = bound_x1, bound_y1, bound_x2, bound_y2

                # Collect words fully inside table bbox
                table_words = []
                for w in words:
                    wx1, wy1, wx2, wy2 = w[:4]
                    if wx1 >= tb_x1 and wx2 <= tb_x2 and wy1 >= tb_y1 and wy2 <= tb_y2:
                        table_words.append((wx1, wy1, wx2, wy2, w[4]))

                if table_words:
                    # header detection
                    min_wy1 = min(w[1] for w in table_words)
                    heights = sorted([(w[3] - w[1]) for w in table_words])
                    median_height = heights[len(heights) // 2] if heights else 12
                    header_threshold = min_wy1 + max(6, median_height * 1.5)
                    header_words = [w for w in table_words if w[1] <= header_threshold]

                    # find TOTAL row to stop before it
                    total_row_y = None
                    for w in table_words:
                        if "TOTAL" in w[4].upper():
                            total_row_y = w[1]
                            break

                    if header_words:
                        header_centers = sorted([((w[0] + w[2]) / 2.0, w[4], w) for w in header_words], key=lambda x: x[0])
                        centers = [c[0] for c in header_centers]

                        # find header column index that matches rule.text_find
                        match_index = None
                        matched_header_word = None
                        for idx, (_, text, word_tuple) in enumerate(header_centers):
                            if rule.text_find.lower().strip() in text.lower().strip():
                                match_index = idx
                                matched_header_word = word_tuple
                                break

                        if match_index is not None:
                            # calculate column bounds
                            col_left = tb_x1
                            col_right = tb_x2
                            if match_index == 0:
                                if len(centers) > 1:
                                    col_right = (centers[0] + centers[1]) / 2.0
                            elif match_index == len(centers) - 1:
                                col_left = (centers[-2] + centers[-1]) / 2.0
                            else:
                                col_left = (centers[match_index - 1] + centers[match_index]) / 2.0
                                col_right = (centers[match_index] + centers[match_index + 1]) / 2.0

                            header_x1 = matched_header_word[0]
                            col_width_est = col_right - col_left
                            left_margin = max(col_width_est * 0.15, 5.0)
                            col_left = max(tb_x1, min(col_left - left_margin, header_x1 - 3))
                            right_margin = max(col_width_est * 0.10, 3.0)
                            col_right = min(tb_x2, col_right + right_margin)

                            header_bottom = max(w[3] for w in header_words)

                            # group words by row using center Y
                            row_groups = {}
                            for w in table_words:
                                wx1, wy1, wx2, wy2, wtext = w
                                wy_center = (wy1 + wy2) / 2.0
                                wx_center = (wx1 + wx2) / 2.0
                                if wy_center >= header_bottom - 1:
                                    if total_row_y is not None and wy_center >= total_row_y - 2:
                                        continue
                                    if (wx_center >= col_left + 1.0) and (wx_center <= col_right - 1.0):
                                        row_key = round(wy_center / 5) * 5
                                        row_groups.setdefault(row_key, []).append((wx1, wy1, wx2, wy2, wtext))

                            for row_words in row_groups.values():
                                if not row_words:
                                    continue
                                min_x = min(w[0] for w in row_words)
                                min_y = min(w[1] for w in row_words)
                                max_x = max(w[2] for w in row_words)
                                max_y = max(w[3] for w in row_words)
                                rect = fitz.Rect(min_x - 2, min_y - 1, max_x + 2, max_y + 1)
                                annot = page.add_redact_annot(rect)
                                annot.set_colors(fill=(1, 1, 1))
                                annot.update()

                            page.apply_redactions()
                continue

            # 2) COLUMN BY NAME: find header and redact words in that column below header
            if rule.ruleType == "column_by_name" and rule.text_find:
                header_match = None
                for w in words:
                    wx1, wy1, wx2, wy2 = w[:4]
                    wtext = w[4]
                    if rule.text_find.lower().strip() in wtext.lower().strip():
                        if header_match is None or wy1 < header_match[1]:
                            header_match = (wx1, wy1, wx2, wy2, wtext)

                if header_match:
                    hx1, hy1, hx2, hy2, header_text = header_match
                    hx1, hy1, hx2, hy2, _ = header_match
                    col_width = (hx2 - hx1)
                    col_left = max(0, hx1 - col_width * 0.3)
                    col_right = hx2 + col_width * 0.3

                    for word in words:
                        wx1, wy1, wx2, wy2 = word[:4]
                        wy_center = (wy1 + wy2) / 2.0
                        if wy_center >= hy2 - 1 and (wx1 <= col_right and wx2 >= col_left):
                            rect = fitz.Rect(wx1, wy1, wx2, wy2)
                            annot = page.add_redact_annot(rect)
                            annot.set_colors(fill=(1, 1, 1))
                            annot.update()

                    page.apply_redactions()
                continue

            # 2.5) DATE-SHIFT: find dates in the bounding box and replace by date + shift days
            if rule.ruleType in ("date-shift", "shift_days"):
                pattern = getattr(rule, 'customPattern', None) or r"\d{2}/\d{2}/\d{2,4}"
                try:
                    date_re = re.compile(pattern)
                except Exception as e:
                    continue

                shift_days = int(getattr(rule, 'dateShiftDays', -7))
                replacements = []

                for w in words:
                    wx1, wy1, wx2, wy2 = w[:4]
                    wtext = w[4]
                    
                    if wx2 < bound_x1 or wx1 > bound_x2 or wy2 < bound_y1 or wy1 > bound_y2:
                        continue
                    
                    m = date_re.search(wtext)
                    if not m:
                        continue
                    
                    orig_date = m.group(0)
                    
                    if not date_re.fullmatch(wtext.strip()):
                        if len(orig_date) < 8:
                            continue
                    
                    parsed = None
                    output_fmt = None
                    
                    date_formats = [
                        ("%m/%d/%Y", "%m/%d/%Y"),
                        ("%m/%d/%y", "%m/%d/%y"),
                        ("%Y-%m-%d", "%Y-%m-%d"),
                        ("%d/%m/%Y", "%d/%m/%Y"),
                        ("%d/%m/%y", "%d/%m/%y"),
                    ]
                    
                    for input_fmt, out_fmt in date_formats:
                        try:
                            parsed = datetime.strptime(orig_date, input_fmt)
                            output_fmt = out_fmt
                            break
                        except Exception:
                            continue
                    
                    if not parsed:
                        continue

                    new_date = parsed + timedelta(days=shift_days)
                    new_str = new_date.strftime(output_fmt)

                    # Get font info
                    blocks = page.get_text("dict")["blocks"]
                    font_info = None
                    
                    for block in blocks:
                        if block.get("type") == 0:
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    sx1, sy1, sx2, sy2 = span["bbox"]
                                    if (sx1 <= wx1 and wx2 <= sx2 and sy1 <= wy1 and wy2 <= sy2):
                                        font_info = {
                                            "font": span.get("font", "helv"),
                                            "size": span.get("size", 10),
                                            "color": span.get("color", 0),
                                        }
                                        break
                                if font_info:
                                    break
                        if font_info:
                            break
                    
                    if not font_info:
                        font_size = (wy2 - wy1) * 1.0
                        font_info = {
                            "font": "helv",
                            "size": font_size,
                            "color": 0,
                        }

                    font_name = font_info.get("font", "helv")
                    font_size = float(font_info.get("size", max(8, (wy2 - wy1) * 0.75)))
                    try:
                        text_width = fitz.get_text_length(orig_date, fontname=font_name, fontsize=font_size)
                    except Exception:
                        text_width = len(orig_date) * (font_size * 0.5)

                    padding_x = 0.2
                    desired_w = text_width + padding_x * 2
                    orig_w = (wx2 - wx1)
                    if desired_w < orig_w - 0.5:
                        left = wx1 + max(0.05, (orig_w - desired_w) / 2.0)
                        right = left + desired_w
                    else:
                        left = wx1 + 0.05
                        right = wx2 - 0.05

                    desired_h = max(font_size * 0.9, (wy2 - wy1) * 0.25)
                    orig_h = (wy2 - wy1)
                    if desired_h < orig_h:
                        top = wy1 + max(0.02, (orig_h - desired_h) / 2.0)
                        bottom = top + desired_h
                    else:
                        top = wy1 + 0.02
                        bottom = wy2 - 0.02

                    precise_rect = fitz.Rect(left, top, right, bottom)
                    replacements.append((precise_rect, new_str, orig_date, font_info, (wx1, wy1, wx2, wy2)))

                if replacements:
                    # Redact
                    for rect, new_text, orig_text, font_info, orig_coords in replacements:
                        annot = page.add_redact_annot(rect)
                        annot.set_colors(fill=(1, 1, 1))
                        annot.update()
                    
                    page.apply_redactions()
                    
                    # Insert
                    for rect, new_text, orig_text, font_info, (ox1, oy1, ox2, oy2) in replacements:
                        try:
                            color_int = font_info["color"]
                            r = ((color_int >> 16) & 0xFF) / 255.0
                            g = ((color_int >> 8) & 0xFF) / 255.0
                            b = (color_int & 0xFF) / 255.0
                            color_tuple = (r, g, b)
                            
                            font_size = font_info["size"]
                            insert_font_size = float(font_size) * 0.85
                            rect_height = oy2 - oy1
                            
                            baseline_x = ox1
                            baseline_y = oy1 + (rect_height * 0.76)
                            
                            fonts_to_try = ["helv", "times", "cour"]
                            inserted = False
                            
                            for try_font in fonts_to_try:
                                try:
                                    text_width = fitz.get_text_length(new_text, fontname=try_font, fontsize=insert_font_size)
                                    orig_width = ox2 - ox1
                                    x_offset = (orig_width - text_width) / 2
                                    insert_x = baseline_x + x_offset
                                    
                                    page.insert_text(
                                        (insert_x, baseline_y),
                                        new_text,
                                        fontname=try_font,
                                        fontsize=insert_font_size,
                                        color=color_tuple
                                    )
                                    
                                    inserted = True
                                    break
                                    
                                except Exception as e:
                                    continue
                            
                            if not inserted:
                                textbox_rect = fitz.Rect(ox1, oy1, ox2, oy2)
                                rc = page.insert_textbox(
                                    textbox_rect,
                                    new_text,
                                    fontsize=insert_font_size,
                                    fontname="helv",
                                    color=color_tuple,
                                    align=fitz.TEXT_ALIGN_CENTER
                                )
                                    
                        except Exception as e:
                            pass
                
                continue

            # 3) Generic text-based rules (all-text, full-line, full-column, regex etc.)
            x1, y1, x2, y2 = bound_x1, bound_y1, bound_x2, bound_y2
            
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
            if rule.ruleType != "all-text":
                space = 40
            
            for word in words:
                word_x1, word_y1, word_x2, word_y2 = word[:4]
                if (is_point_in_rectangle(x1 + space, y1 - 1, x2 + 2, y2 + 1, word_x1, word_y1)):
                    rect = fitz.Rect(word_x1, word_y1, word_x2, word_y2)
                    annot = page.add_redact_annot(rect)
                    annot.update()
                    page.apply_redactions()

            rect = fitz.Rect(word_x1, word_y1, word_x2, word_y2)
            shape = page.new_shape()
            shape.commit()

        output_buffer = io.BytesIO()
        doc.save(output_buffer)
        return output_buffer.getvalue()

    finally:
        doc.close()

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

@app.post("/redact-pdf-advanced-template")
async def redact_pdf_advanced_template(
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
            result = process_pdf_advanced_template(pdf_content, request_obj.rules)
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
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=3000)#