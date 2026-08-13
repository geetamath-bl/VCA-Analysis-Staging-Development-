# api/index.py

import os
import sys
from pathlib import Path

# ============================================================
# Environment configuration
# ============================================================

os.environ["LTP_REMOTE_SERVER"] = "https://api.languagetool.org"

import static_ffmpeg
static_ffmpeg.add_paths()

# ============================================================
# Project paths
# ============================================================

# This file is at: <project-root>/api/index.py
BASE_DIR = Path(__file__).resolve().parent.parent

VCA_CODE_DIR = BASE_DIR / "vca_code"
API_DIR = BASE_DIR / "api"

# Add to sys.path so imports work in serverless environment
for path in [VCA_CODE_DIR, API_DIR]:
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)

# ============================================================
# Import FastAPI app from vca_code.main
# ============================================================

from main import app  # This imports app from vca_code/main.py