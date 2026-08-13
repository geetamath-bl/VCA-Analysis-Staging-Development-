# vca_code/main.py

import os
import sys
from pathlib import Path

# Environment configuration
os.environ["LTP_REMOTE_SERVER"] = "https://api.languagetool.org"

import static_ffmpeg
static_ffmpeg.add_paths()

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
VCA_CODE_DIR = BASE_DIR / "vca_code"
API_DIR = BASE_DIR / "api"
FRONTEND_DIR = BASE_DIR / "frontend"

# Add to sys.path
for path in [VCA_CODE_DIR, API_DIR]:
    path_string = str(path)
    if path_string not in sys.path:
        sys.path.insert(0, path_string)

# Import router
from router import router as vca_router  # This imports from api/router.py

# FastAPI app
app = FastAPI(
    title="Verbal Communication Ability (VCA) API",
    description="AI-based Verbal Communication Analyzer",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frontend static files
if FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIR),
        name="static"
    )

# Include router
app.include_router(vca_router)

# Frontend home page
@app.get("/")
async def serve_frontend():
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        return {
            "status": "success",
            "message": "VCA API is running",
            "docs": "/docs"
        }
    return FileResponse(index_file)

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "VCA API"
    }

# Local development only
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )