import os
import sys
from pathlib import Path
import static_ffmpeg

# ============================================================
# Environment configuration
# ============================================================

# LanguageTool remote API
# This avoids requiring the Java-based local LanguageTool
# server when deployed on Vercel.
os.environ["LTP_REMOTE_SERVER"] = "https://api.languagetool.org"


# ============================================================
# FFmpeg configuration
# ============================================================

# static-ffmpeg is included in requirements.txt.
# This adds the bundled ffmpeg/ffprobe executables to PATH
# so subprocess calls such as "ffmpeg" can find them.

static_ffmpeg.add_paths()


# ============================================================
# FastAPI imports
# ============================================================

import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


# ============================================================
# Project paths
# ============================================================

# main.py is inside:
#
# vca-without-azure/
# └── vca_code/
#     └── main.py
#
# Therefore parent.parent gives:
#
# vca-without-azure/

BASE_DIR = Path(__file__).resolve().parent.parent

VCA_CODE_DIR = BASE_DIR / "vca_code"
API_DIR = BASE_DIR / "api"
FRONTEND_DIR = BASE_DIR / "frontend"


# ============================================================
# Python module paths
# ============================================================

# Make vca_code and api modules importable.

for path in [VCA_CODE_DIR, API_DIR]:
    path_string = str(path)

    if path_string not in sys.path:
        sys.path.insert(0, path_string)


# ============================================================
# Import VCA router
# ============================================================

from router import router as vca_router


# ============================================================
# FastAPI application
# ============================================================

app = FastAPI(
    title="Verbal Communication Ability (VCA) API",
    description="AI-based Verbal Communication Analyzer",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Frontend static files
# ============================================================

# Your frontend folder contains:
#
# frontend/
# ├── index.html
# ├── script.js
# └── style.css
#
# They will be available through /static/...

if FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIR),
        name="static"
    )


# ============================================================
# VCA API routes
# ============================================================

# This includes:
#
# POST /vca/analyze

app.include_router(vca_router)


# ============================================================
# Frontend home page
# ============================================================

@app.get("/")
async def serve_frontend():
    """
    Serve the VCA frontend application.
    """

    index_file = FRONTEND_DIR / "index.html"

    if not index_file.exists():
        return {
            "status": "success",
            "message": "VCA API is running",
            "docs": "/docs"
        }

    return FileResponse(index_file)


# ============================================================
# Health check
# ============================================================

@app.get("/health")
async def health_check():
    """
    Simple health check to verify that the FastAPI
    application is running on Vercel.
    """

    return {
        "status": "healthy",
        "service": "VCA API"
    }


# ============================================================
# Local development
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )