

import json
from config import Config
from logger_setup import PipelineLogger
from vocab_grammar_analyzer import VocabGrammarAnalyzer

cfg = Config()
logger = PipelineLogger(log_folder=cfg.log_folder, total_steps=8)

analyzer = VocabGrammarAnalyzer(cfg, logger)

with open(cfg.transcript_folder / "array_vs_linkedlist_1_transcript.txt", encoding="utf-8") as f:
    transcript_text = f.read()

vocab_metrics = analyzer.analyze(transcript_text)
analyzer.save_metrics(vocab_metrics, "array_vs_linkedlist_1")
analyzer.close()

print("\nVocab/grammar metrics:")
print(json.dumps(vocab_metrics, indent=2))