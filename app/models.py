from pydantic import BaseModel
from typing import List


class RedactArea(BaseModel):
    x: float
    y: float
    width: float
    height: float


class RedactRule(BaseModel):
    page: int
    area: RedactArea


class RedactPdfRequest(BaseModel):
    source_uri: str
    rules: List[RedactRule]
