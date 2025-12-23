import fitz
import io


def redact_pdf(pdf_bytes: bytes, rules):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for rule in rules:
        page = doc[rule.page]
        x1 = rule.area.x
        y1 = rule.area.y
        x2 = x1 + rule.area.width
        y2 = y1 + rule.area.height

        rect = fitz.Rect(x1, y1, x2, y2)
        page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions()

    buffer = io.BytesIO()
    doc.save(buffer)
    doc.close()
    return buffer.getvalue()
