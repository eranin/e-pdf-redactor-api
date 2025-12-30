from fastapi import FastAPI
from app.api import router

app = FastAPI(title="PDF Redact Service")
app.include_router(router)
