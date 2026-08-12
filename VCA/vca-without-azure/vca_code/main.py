# File: vca_code/main.py

import sys
from pathlib import Path

# ---------------------------------------------------------
# Setup directory paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

vca_code_path = BASE_DIR / "vca_code"
api_path = BASE_DIR / "api"
frontend_path = BASE_DIR / "frontend"

for p in [str(vca_code_path), str(api_path)]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------
# Initialize static FFmpeg BEFORE importing router
# ---------------------------------------------------------

import static_ffmpeg

static_ffmpeg.add_paths()

# Debug: verify FFmpeg is available
import shutil

print("FFmpeg path:", shutil.which("ffmpeg"))


# ---------------------------------------------------------
# FastAPI imports
# ---------------------------------------------------------

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


# ---------------------------------------------------------
# Import router AFTER FFmpeg initialization
# ---------------------------------------------------------

from router import router as vca_router


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="Verbal Communication Ability (VCA) API"
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Mount VCA API
# ---------------------------------------------------------

app.include_router(vca_router)


# ---------------------------------------------------------
# Serve Frontend
# ---------------------------------------------------------

@app.get("/")
async def serve_frontend():
    return FileResponse(frontend_path / "index.html")


# ---------------------------------------------------------
# Local development
# ---------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )