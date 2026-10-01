# librosa_compat.py
# ------------------------------------------------------------------------------
# librosa loads its submodules lazily from ".pyi" stub files. Vercel strips
# ".pyi" files from installed packages, so "import librosa" fails there with
# "Cannot load imports from non-existent stub".
#
# This module keeps copies of those stubs in librosa_stubs/ (saved as
# ".pyi.txt" so they are not stripped) and, when a real stub is missing,
# writes the copy to a temp directory and loads it from there.
#
# Import this module before importing librosa. Locally, where the real stubs
# exist, it changes nothing.
# ------------------------------------------------------------------------------

import os
import tempfile
from pathlib import Path

import lazy_loader

STUB_BACKUP_DIR = Path(__file__).resolve().parent / "librosa_stubs"
STUB_TEMP_DIR = Path(tempfile.gettempdir()) / "librosa_stubs"

_original_attach_stub = lazy_loader.attach_stub


def _attach_stub_with_fallback(package_name: str, filename: str):
    stub_path = os.path.splitext(filename)[0] + ".pyi"
    backup_path = STUB_BACKUP_DIR / f"{package_name}.pyi.txt"

    if not os.path.exists(stub_path) and backup_path.exists():
        STUB_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        temp_stub = STUB_TEMP_DIR / f"{package_name}.pyi"
        temp_stub.write_text(backup_path.read_text())
        # lazy_loader uses a path ending in "i" as the stub file directly.
        filename = str(temp_stub)

    return _original_attach_stub(package_name, filename)


lazy_loader.attach_stub = _attach_stub_with_fallback
