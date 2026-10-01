import os
import sys
import stat
from pathlib import Path

# Environment configuration
os.environ["LTP_REMOTE_SERVER"] = "https://api.languagetool.org"

# ==============================================================================
# 1. SETUP PATHS & BUNDLED FFMPEG BINARY
# ==============================================================================
# Determine Root Directory safely across local and Vercel environments
CURRENT_FILE = Path(__file__).resolve()
BASE_DIR = CURRENT_FILE.parent.parent

# Fallback: If bin doesn't exist relative to file, check current working directory
if not (BASE_DIR / "bin").exists():
    BASE_DIR = Path(os.getcwd())

FFMPEG_BIN = BASE_DIR / "bin" / "ffmpeg"

# Configure FFmpeg in PATH
if FFMPEG_BIN.exists():
    # Attempt to set permissions if allowed, but ignore if filesystem is read-only
    try:
        st = os.stat(FFMPEG_BIN)
        os.chmod(FFMPEG_BIN, st.st_mode | stat.S_IEXEC)
    except Exception as e:
        print(f"Notice: Could not modify permissions on {FFMPEG_BIN}: {e}")

    # Add bin directory to PATH so pydub / ffmpeg-python find it
    bin_dir_str = str(FFMPEG_BIN.parent)
    if bin_dir_str not in os.environ["PATH"]:
        os.environ["PATH"] = bin_dir_str + os.pathsep + os.environ["PATH"]
else:
    print(f"Warning: FFmpeg binary not found at {FFMPEG_BIN}")
# ==============================================================================

# Project paths
VCA_CODE_DIR = BASE_DIR / "vca_code"
API_DIR = BASE_DIR / "api"
FRONTEND_DIR = BASE_DIR / "frontend"

# Ensure imports resolve cleanly
for path in [BASE_DIR, VCA_CODE_DIR, API_DIR]:
    path_string = str(path)
    if path_string not in sys.path:
        sys.path.insert(0, path_string)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Restore librosa's stub files on Vercel (must run before librosa is imported)
import librosa_compat  # noqa: F401

# Import router safely
try:
    from router import router as vca_router
except ModuleNotFoundError:
    from api.router import router as vca_router

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