# File: Repo/VCA/vca-without-azure/vca_code/test_logger.py
# This file is a simple test script to verify that the logger is working correctly.

from config import Config
from logger_setup import PipelineLogger

cfg = Config()
logger = PipelineLogger(log_folder=cfg.log_folder, total_steps=8)  # 8 steps for this variant

logger.step("Testing logger for vca-without-azure")
logger.info("This is a test log line.")
logger.warning("This is a test warning.")