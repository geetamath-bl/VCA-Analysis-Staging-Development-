import os
import sys
from pathlib import Path

# Force language_tool_python to use remote API
# This avoids requiring Java on Vercel.
os.environ["LTP_REMOTE_SERVER"] = "https://api.languagetool.org"

# Make FFmpeg available on Vercel
import static_ffmpeg

static_ffmpeg.add_paths()

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


# ============================================================
# Setup directory paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

vca_code_path = BASE_DIR / "vca_code"
api_path = BASE_DIR / "api"
frontend_path = BASE_DIR / "frontend"


# Add project folders to Python path
for p in [str(vca_code_path), str(api_path)]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ============================================================
# Import VCA Router
# ============================================================

from router import router as vca_router


# ============================================================
# Create FastAPI Application
# ============================================================

app = FastAPI(
    title="Verbal Communication Ability (VCA) API"
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
# Serve Frontend Static Files
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory=frontend_path),
    name="static"
)


# ============================================================
# Mount VCA API Routes
# ============================================================

app.include_router(vca_router)


# ============================================================
# Serve Frontend
# ============================================================

@app.get("/")
async def serve_frontend():
    return FileResponse(frontend_path / "index.html")


# ============================================================
# Local Development
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )