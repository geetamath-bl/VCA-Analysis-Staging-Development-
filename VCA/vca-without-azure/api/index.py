import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

VCA_CODE_DIR = BASE_DIR / "vca_code"

if str(VCA_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(VCA_CODE_DIR))

from main import app