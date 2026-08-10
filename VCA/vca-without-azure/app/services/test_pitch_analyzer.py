# File:  Repo/VCA/vca-without-azure/vca_code/test_pitch_analyzer.py
# This script tests the PitchAnalyzer class by computing pitch and volume
#      variability metrics from a sample audio file.


import json
from config import Config
from logger_setup import PipelineLogger
from pitch_analyzer import PitchAnalyzer

cfg = Config()
logger = PipelineLogger(log_folder=cfg.log_folder, total_steps=8)

analyzer = PitchAnalyzer(cfg, logger)

wav_file = cfg.audio_input_folder / "array_vs_linkedlist_1.wav"
pitch_metrics = analyzer.analyze(wav_file)
analyzer.save_metrics(pitch_metrics, "array_vs_linkedlist_1_pitch_metrics")

print("\nPitch metrics:")
print(json.dumps(pitch_metrics, indent=2))