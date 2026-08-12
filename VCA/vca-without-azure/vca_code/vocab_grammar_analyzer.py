# File: Repo/VCA/vca-without-azure/vca_code/vocab_grammar_analyzer.py
# This module provides the VocabGrammarAnalyzer class, 
#  which analyzes a transcript for grammar errors and vocabulary 
#  richness using LanguageTool (local, no Azure service involved).


import re
import json
from pathlib import Path
from language_tool_python import LanguageToolPublicAPI

from config import Config
from logger_setup import PipelineLogger


class VocabGrammarAnalyzer:
    """
    Analyzes a transcript for grammar errors and vocabulary richness
    using LanguageTool (local, no Azure service involved).
    """

    def __init__(self, config: Config, logger: PipelineLogger):
        self.config = config
        self.logger = logger
        self.tool = LanguageToolPublicAPI('en-US')

    def analyze(self, transcript_text: str) -> dict:
        """
        Runs grammar checking and vocabulary richness analysis on the given transcript.
        Returns a dict of computed metrics.
        """
        self.logger.step("Analyzing vocabulary and grammar")

        if not transcript_text.strip():
            self.logger.warning("  Empty transcript — skipping vocab/grammar analysis.")
            return {}

        grammar_error_count, grammar_issues = self._check_grammar(transcript_text)
        vocab_metrics = self._analyze_vocabulary(transcript_text)

        total_words = vocab_metrics["total_words"]
        errors_per_100_words = (grammar_error_count / total_words) * 100 if total_words > 0 else 0

        metrics = {
            **vocab_metrics,
            "grammar_error_count": grammar_error_count,
            "errors_per_100_words": round(errors_per_100_words, 2)
        }

        self.logger.info(
            f"  TTR: {metrics['ttr']}, Grammar errors: {grammar_error_count}, "
            f"Errors/100 words: {metrics['errors_per_100_words']}"
        )

        # Log individual grammar issues at a finer detail level (useful for debugging/review)
        for issue in grammar_issues:
            self.logger.info(f"    - {issue}")

        return metrics

    def _check_grammar(self, transcript_text: str) -> tuple[int, list]:
        """Runs LanguageTool grammar check. Returns (error_count, list_of_issue_descriptions)."""
        matches = self.tool.check(transcript_text)
        issues = [f"{m.rule_id}: {m.message}" for m in matches]
        return len(matches), issues

    def _analyze_vocabulary(self, transcript_text: str) -> dict:
        """Computes Type-Token Ratio (TTR) and average word length."""
        words = re.findall(r"\b[a-zA-Z']+\b", transcript_text.lower())
        total_words = len(words)
        unique_words = len(set(words))
        ttr = (unique_words / total_words) if total_words > 0 else 0
        avg_word_length = sum(len(w) for w in words) / total_words if total_words > 0 else 0

        return {
            "total_words": total_words,
            "unique_words": unique_words,
            "ttr": round(ttr, 3),
            "avg_word_length": round(avg_word_length, 2)
        }

    def save_metrics(self, metrics: dict, base_filename: str) -> Path:
        """Saves the vocab/grammar metrics dict as JSON in /json_output."""
        json_path = self.config.json_output_folder / f"{base_filename}_vocab_metrics.json"

        with open(json_path, "w") as f:
            json.dump(metrics, f, indent=2)

        self.logger.info(f"  Vocab/grammar metrics saved to: {json_path}")
        return json_path

    def close(self):
        """Releases the LanguageTool resource. Call this when done with the analyzer."""
        self.tool.close()