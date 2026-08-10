# File: Repo/VCA/vca-without-azure/vca_code/scorer.py
# This script computes the composite Verbal Communication Ability (VCA) score
# It uses the VCAScorer class to calculate sub-scores for pace, fluency, filler words,
# expressiveness (pitch/tone), and vocabulary/grammar, and then combines them into an
# overall score. The final report is saved as a JSON file in the /json_output folder

# Approach taken:
# 1. Define a VCAScorer class that takes in metrics from the four dimensions
# 2. Each dimension has its own scoring function that returns a score between 0-100
# 3. The overall score is computed as a weighted sum of the sub-scores  

import json
from pathlib import Path

from config import Config
from logger_setup import PipelineLogger


class VCAScorer:
    """
    Computes the composite Verbal Communication Ability (VCA) score
    from the four metric dimensions: pace, fluency, filler words,
    expressiveness (pitch/tone), and vocabulary/grammar.
    """

    WEIGHTS = {
        "pace": 0.20,
        "fluency": 0.25,
        "filler": 0.15,
        "expressiveness": 0.20,
        "vocab_grammar": 0.20
    }

    def __init__(self, config: Config, logger: PipelineLogger):
        self.config = config
        self.logger = logger

    def compute_score(self, metrics: dict, pitch_metrics: dict, vocab_metrics: dict) -> dict:
        """
        Computes individual sub-scores and the weighted overall VCA score.
        Returns a dict containing all sub-scores, the overall score, and a rating label.
        """
        self.logger.step("Computing composite Verbal Communication Ability (VCA) score")

        pace_score = self._score_pace(metrics.get("wpm", 0))
        fluency_score = self._score_fluency(
            metrics.get("num_pauses", 0),
            metrics.get("long_pauses", 0),
            metrics.get("total_duration_sec", 0)
        )
        filler_score = self._score_filler_words(metrics.get("filler_ratio", 0))
        expressiveness_score = self._score_expressiveness(
            pitch_metrics.get("pitch_cv_percent", 0),
            pitch_metrics.get("volume_cv_percent", 0)
        )
        vocab_grammar_score = self._score_vocab_grammar(
            vocab_metrics.get("ttr", 0),
            vocab_metrics.get("errors_per_100_words", 0)
        )

        overall_score = (
            pace_score * self.WEIGHTS["pace"] +
            fluency_score * self.WEIGHTS["fluency"] +
            filler_score * self.WEIGHTS["filler"] +
            expressiveness_score * self.WEIGHTS["expressiveness"] +
            vocab_grammar_score * self.WEIGHTS["vocab_grammar"]
        )

        rating = self._rating_label(overall_score)

        report = {
            "pace_score": round(pace_score, 1),
            "fluency_score": round(fluency_score, 1),
            "filler_score": round(filler_score, 1),
            "expressiveness_score": round(expressiveness_score, 1),
            "vocab_grammar_score": round(vocab_grammar_score, 1),
            "overall_score": round(overall_score, 1),
            "rating": rating
        }

        self.logger.info(f"  Pace: {report['pace_score']}, Fluency: {report['fluency_score']}, "
                          f"Filler: {report['filler_score']}, Expressiveness: {report['expressiveness_score']}, "
                          f"Vocab/Grammar: {report['vocab_grammar_score']}")
        self.logger.info(f"  OVERALL VCA SCORE: {report['overall_score']}/100 -> {report['rating']}")

        return report

    def _score_pace(self, wpm: float) -> float:
        if 120 <= wpm <= 160:
            return 100
        elif 100 <= wpm < 120 or 160 < wpm <= 180:
            return 80
        elif 80 <= wpm < 100 or 180 < wpm <= 200:
            return 60
        else:
            return 40

    def _score_fluency(self, num_pauses: int, long_pauses: int, total_duration_sec: float) -> float:
        minutes = total_duration_sec / 60 if total_duration_sec > 0 else 1
        pauses_per_min = num_pauses / minutes
        long_pause_penalty = long_pauses * 10

        if pauses_per_min <= 6:
            base = 100
        elif pauses_per_min <= 10:
            base = 80
        elif pauses_per_min <= 15:
            base = 60
        else:
            base = 40

        return max(0, base - long_pause_penalty)

    def _score_filler_words(self, filler_ratio: float) -> float:
        if filler_ratio <= 2:
            return 100
        elif filler_ratio <= 5:
            return 80
        elif filler_ratio <= 8:
            return 60
        elif filler_ratio <= 12:
            return 40
        else:
            return 20

    def _score_expressiveness(self, pitch_cv: float, volume_cv: float) -> float:
        def sub_score(cv, low, high):
            if low <= cv <= high:
                return 100
            elif cv < low:
                return max(30, 100 - (low - cv) * 3)
            else:
                return max(30, 100 - (cv - high) * 1.5)

        pitch_component = sub_score(pitch_cv, 15, 35)
        volume_component = sub_score(volume_cv, 20, 50)
        return (pitch_component * 0.6) + (volume_component * 0.4)

    def _score_vocab_grammar(self, ttr: float, errors_per_100_words: float) -> float:
        if 0.5 <= ttr <= 0.75:
            ttr_score = 100
        elif 0.4 <= ttr < 0.5 or 0.75 < ttr <= 0.85:
            ttr_score = 80
        else:
            ttr_score = 60

        if errors_per_100_words <= 2:
            grammar_score = 100
        elif errors_per_100_words <= 5:
            grammar_score = 80
        elif errors_per_100_words <= 8:
            grammar_score = 60
        elif errors_per_100_words <= 12:
            grammar_score = 40
        else:
            grammar_score = 20

        return (ttr_score * 0.5) + (grammar_score * 0.5)

    def _rating_label(self, score: float) -> str:
        if score >= 85:
            return "Excellent"
        elif score >= 70:
            return "Good"
        elif score >= 50:
            return "Fair"
        else:
            return "Needs Improvement"

    def save_report(self, report: dict, base_filename: str) -> Path:
        """Saves the final VCA score report as JSON in /json_output."""
        json_path = self.config.json_output_folder / f"{base_filename}_score_report.json"

        with open(json_path, "w") as f:
            json.dump(report, f, indent=2)

        self.logger.info(f"  Score report saved to: {json_path}")
        return json_path