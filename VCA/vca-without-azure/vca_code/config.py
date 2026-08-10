# File: Repo/VCA/vca-without-azure/vca_code/config.py

# This file is responsible for loading configuration settings from a .env file,
# ensuring that required folders exist, and validating the presence of necessary environment variables.

import os
from dotenv import load_dotenv
from pathlib import Path


class Config:
    """
    Centralized configuration loader for the non-Azure (Gemini-based) variant.
    Reads all settings and credentials from the .env file.
    """

    def __init__(self, env_path: str = None):

        # Load .env from the VCA project root
        if env_path is None:
            env_path = Path(__file__).resolve().parents[3] / ".env"
       

        load_dotenv(dotenv_path=env_path)

        # Gemini settings
        self.gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
        self.gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash") 

        # Project folder structure (relative to project root, one level above /vca_code)
        self.project_root: Path = Path(__file__).resolve().parent.parent
        self.audio_input_folder: Path = self.project_root / "audio_files"
        self.transcript_folder: Path = self.project_root / "transcript"
        self.json_output_folder: Path = self.project_root / "json_output"
        self.log_folder: Path = self.project_root / "log"

        self._ensure_folders_exist()
        self._validate()

    def _ensure_folders_exist(self):
        """Create required folders if they don't already exist."""
        for folder in [
            self.audio_input_folder,
            self.transcript_folder,
            self.json_output_folder,
            self.log_folder,
        ]:
            folder.mkdir(parents=True, exist_ok=True)

    def _validate(self):
        """Basic sanity check that required values are present."""
        required = {
            "GEMINI_API_KEY": self.gemini_api_key,
        }

        missing = [key for key, value in required.items() if not value]

        if missing:
            raise EnvironmentError(
                f"Missing required environment variables in .env: {', '.join(missing)}"
            )

