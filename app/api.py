from fastapi import APIRouter
from app.models import RedactRequest
from app.services.redact_service import handle_redact

router = APIRouter()


@router.post("/redact")
def redact(request: RedactRequest):
    uri = handle_redact(request)
    return {
        "status": "success",
        "redacted_uri": uri
    }
