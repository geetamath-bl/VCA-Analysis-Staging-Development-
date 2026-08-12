import sys
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles  # <--- Added import

# Setup directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
vca_code_path = BASE_DIR / "vca_code"
api_path = BASE_DIR / "api"
frontend_path = BASE_DIR / "frontend"

for p in [str(vca_code_path), str(api_path)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from router import router as vca_router

app = FastAPI(title="Verbal Communication Ability (VCA) API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API
app.include_router(vca_router)

# --- FIX: Serve all static assets (CSS, JS, images, etc.) from frontend folder ---
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# Serve Frontend HTML
@app.get("/")
async def serve_frontend():
    return FileResponse(frontend_path / "index.html")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)