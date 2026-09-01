"""FastAPI app for CMMI ITSM Assessment MVP."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import question_bank, assessments, sessions

app = FastAPI(title="CMMI ITSM Assessment API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3002",
        "http://localhost:5555",
        "http://localhost:5556",
        "http://localhost:5557",
        "http://192.168.0.3:3000",
        "http://192.168.0.3:3002",
        "http://192.168.0.3:5555",
        "http://192.168.0.3:5556",
        "http://192.168.0.3:5557",
        "*",  # allow all for now — tighten once MVP is solid
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(question_bank.router)
app.include_router(assessments.router)
app.include_router(sessions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}