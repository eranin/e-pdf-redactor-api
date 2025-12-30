from fastapi import APIRouter
from app.models import RedactPdfRequest
from app.services.redact_service import handle_redact_pdf

router = APIRouter()


@router.post("/redact-pdf")
def redact_pdf(request: RedactPdfRequest):
    try:
        uri = handle_redact_pdf(request)
        response = {
            "status": "success",
            "redacted_uri": uri
        }
        return response
    except Exception as e:
        raise e
