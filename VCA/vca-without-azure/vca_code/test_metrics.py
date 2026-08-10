# File: Repo/VCA/vca-without-azure/vca_code/test_metrics.py
# This script tests the MetricsCalculator class by computing metrics 
#           from a sample transcript and audio file.

from config import Config
from logger_setup import PipelineLogger
from metrics_calculator import MetricsCalculator

cfg = Config()
logger = PipelineLogger(log_folder=cfg.log_folder, total_steps=8)

with open(cfg.transcript_folder / "array_vs_linkedlist_1_transcript.txt", encoding="utf-8") as f:
    transcript_text = f.read()

wav_file = cfg.audio_input_folder / "array_vs_linkedlist_1.wav"

calculator = MetricsCalculator(cfg, logger)
metrics = calculator.compute_metrics(transcript_text, wav_file)
calculator.save_metrics(metrics, "array_vs_linkedlist_1")

print("\nComputed metrics:")
import json
print(json.dumps(metrics, indent=2))