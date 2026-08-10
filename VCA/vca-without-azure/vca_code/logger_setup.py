# vca_code/logger_setup.py
# This module sets up logging for the VCA pipeline, allowing logs to be written to both 
# the console and a timestamped log file.

import logging
import sys
from datetime import datetime
from pathlib import Path


class PipelineLogger:
    """
    Sets up logging that writes simultaneously to:
      - the console (for real-time progress visibility)
      - a timestamped log file in the /log folder

    Also provides a helper method to log numbered pipeline steps
    (e.g., "Step 3/10: Uploading to blob storage...").
    """

    def __init__(self, log_folder: Path, total_steps: int = 10):
        self.log_folder = log_folder
        self.total_steps = total_steps
        self.current_step = 0

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = self.log_folder / f"vca_run_{timestamp}.log"

        self.logger = logging.getLogger("VCA_Pipeline")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()  # avoid duplicate handlers if re-instantiated

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler
        file_handler = logging.FileHandler(self.log_file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        self.info(f"Log file created at: {self.log_file_path}")

    def step(self, step_description: str):
        """Log the start of a new numbered pipeline step."""
        self.current_step += 1
        message = f"[STEP {self.current_step}/{self.total_steps}] {step_description}"
        self.logger.info(message)

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def get_log_file_path(self) -> Path:
        return self.log_file_path