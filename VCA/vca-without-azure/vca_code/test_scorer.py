# File : Repo/VCA/vca-without-azure/vca_code/test_scorer.py
# This script is used to test the VCA scoring functionality. 
# It loads sample metrics from JSON files, computes the VCA score using 
# the VCAScorer class, and saves the report.

import json
from config import Config
from logger_setup import PipelineLogger
from scorer import VCAScorer

cfg = Config()
logger = PipelineLogger(log_folder=cfg.log_folder, total_steps=8)

with open(cfg.json_output_folder / "array_vs_linkedlist_1_metrics.json") as f:
    metrics = json.load(f)
with open(cfg.json_output_folder / "array_vs_linkedlist_1_pitch_metrics.json") as f:
    pitch_metrics = json.load(f)
with open(cfg.json_output_folder / "array_vs_linkedlist_1_vocab_metrics.json") as f:
    vocab_metrics = json.load(f)

scorer = VCAScorer(cfg, logger)
report = scorer.compute_score(metrics, pitch_metrics, vocab_metrics)
scorer.save_report(report, "array_vs_linkedlist_1")  

print("\nFinal VCA Score Report:")
print(json.dumps(report, indent=2))