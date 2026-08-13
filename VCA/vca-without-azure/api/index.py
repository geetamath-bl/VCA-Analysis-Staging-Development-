# api/index.py  (minimal version)

import os
import sys
from pathlib import Path

os.environ["LTP_REMOTE_SERVER"] = "https://api.languagetool.org"

import static_ffmpeg
static_ffmpeg.add_paths()

BASE_DIR = Path(__file__).resolve().parent.parent
VCA_CODE_DIR = BASE_DIR / "vca_code"
API_DIR = BASE_DIR / "api"

for path in [VCA_CODE_DIR, API_DIR]:
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)

from main import app  # this `app` is used by Vercel