# File: Repo/VCA/vca-without-azure/vca_code/test_readiness.py
# This file is a simple test script to verify that the Gemini API readiness checks
#  are functioning correctly. It will attempt to validate the Gemini API key and
#  confirm that the API is reachable.

from config import Config
from logger_setup import PipelineLogger
from gemini_readiness import GeminiReadinessChecker

cfg = Config()
logger = PipelineLogger(log_folder=cfg.log_folder, total_steps=8)

checker = GeminiReadinessChecker(cfg, logger)
result = checker.check_all()

print(f"\nReadiness check result: {'PASS' if result else 'FAIL'}")