# File: Repo/VCA/vca-without-azure/vca_code/metrics_calculator.py
# This module computes speaking pace, pause, and filler word metrics from audio and transcript data.
# It  detects pauses directly from the audio waveform (using librosa), and 
#   computes WPM using total word count from the transcript divided  by total speaking duration


import re
import json
from pathlib import Path
import numpy as np
import librosa

from config import Config
from logger_setup import PipelineLogger


class MetricsCalculator:
    """
    Computes speaking pace, pause, and filler word metrics using:
      - silence detection on the audio waveform (for pauses, speaking duration)
      - word count from the transcript text (for WPM, filler word ratio)

    This replaces the word-timestamp-based approach used in the Azure variant,
    since Gemini's transcription does not provide reliable word-level timestamps.
    """

    FILLER_WORDS = {
        "um", "uh", "umm", "uhh", "like", "you know",
        "actually", "basically", "literally", "so"
    }

    # Silence detection parameters
    TOP_DB = 30                  # threshold (in dB) below reference to consider as silence
    PAUSE_THRESHOLD_SEC = 0.3     # gaps longer than this count as a "pause"
    LONG_PAUSE_THRESHOLD_SEC = 1.5  # pauses longer than this are flagged as "long"

    def __init__(self, config: Config, logger: PipelineLogger):
        self.config = config
        self.logger = logger

    def compute_metrics(self, transcript_text: str, wav_file_path: Path) -> dict:
        """
        Computes WPM, pause statistics, articulation rate, and filler word ratio.
        Combines transcript word count with audio-based silence detection.
        """
        self.logger.step("Computing pace, pause, and filler word metrics")

        words = re.findall(r"\b[a-zA-Z']+\b", transcript_text.lower())
        total_words = len(words)

        if total_words == 0:
            self.logger.warning("  Empty transcript — skipping metrics computation.")
            return {}

        y, sr = librosa.load(str(wav_file_path), sr=None)
        total_duration_sec = librosa.get_duration(y=y, sr=sr)

        non_silent_intervals = librosa.effects.split(y, top_db=self.TOP_DB)
        pauses = self._compute_pauses(non_silent_intervals, sr)

        num_pauses = len(pauses)
        total_pause_time = sum(pauses)
        avg_pause_duration = (total_pause_time / num_pauses) if num_pauses > 0 else 0
        long_pauses = [p for p in pauses if p > self.LONG_PAUSE_THRESHOLD_SEC]

        speaking_time = total_duration_sec - total_pause_time

        wpm = (total_words / total_duration_sec) * 60 if total_duration_sec > 0 else 0
        articulation_rate = (total_words / speaking_time) * 60 if speaking_time > 0 else 0

        filler_count = self._count_filler_words(words)
        filler_ratio = (filler_count / total_words) * 100 if total_words > 0 else 0

        metrics = {
            "total_words": total_words,
            "total_duration_sec": round(total_duration_sec, 2),
            "wpm": round(wpm, 1),
            "articulation_rate": round(articulation_rate, 1),
            "num_pauses": num_pauses,
            "total_pause_time": round(total_pause_time, 2),
            "avg_pause_duration": round(avg_pause_duration, 2),
            "long_pauses": len(long_pauses),
            "filler_count": filler_count,
            "filler_ratio": round(filler_ratio, 1)
        }

        self.logger.info(f"  WPM: {metrics['wpm']}, Pauses: {metrics['num_pauses']}, "
                          f"Filler ratio: {metrics['filler_ratio']}%")

        return metrics

    def _compute_pauses(self, non_silent_intervals: np.ndarray, sr: int) -> list:
        """
        Given librosa's non-silent interval boundaries (in samples),
        computes the gap durations (in seconds) between consecutive
        non-silent segments — i.e., the pauses.
        """
        pauses = []
        for i in range(1, len(non_silent_intervals)):
            prev_end_sample = non_silent_intervals[i - 1][1]
            curr_start_sample = non_silent_intervals[i][0]

            gap_sec = (curr_start_sample - prev_end_sample) / sr
            if gap_sec > self.PAUSE_THRESHOLD_SEC:
                pauses.append(gap_sec)

        return pauses

    def _count_filler_words(self, words: list) -> int:
        """Counts how many words match known filler words."""
        return sum(1 for w in words if w in self.FILLER_WORDS)

    def save_metrics(self, metrics: dict, base_filename: str) -> Path:
        """Saves the computed metrics dict as JSON in /json_output."""
        json_path = self.config.json_output_folder / f"{base_filename}_metrics.json"

        with open(json_path, "w") as f:
            json.dump(metrics, f, indent=2)

        self.logger.info(f"  Metrics saved to: {json_path}")
        return json_path