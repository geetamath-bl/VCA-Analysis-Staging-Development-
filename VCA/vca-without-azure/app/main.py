import sys
from pathlib import Path

# Add 'app/services' directory to sys.path before loading API routes
services_path = Path(__file__).resolve().parent / "services"
if str(services_path) not in sys.path:
    sys.path.insert(0, str(services_path))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router

app = FastAPI(
    title="VCA - Verbal Communication Ability API",
    description="API for Audio Communication Analysis",
    version="1.0.0"
)

# Enable CORS for local UI interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "online", "message": "VCA FastAPI is running"}

app.include_router(api_router)