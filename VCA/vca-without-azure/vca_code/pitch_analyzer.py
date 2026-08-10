# File:  Repo/VCA/vca-without-azure/vca_code/pitch_analyzer.py
# This module contains the PitchAnalyzer class, which performs 
#      pitch and volume variability analysis on audio files using librosa.

import json
from pathlib import Path
import numpy as np
import librosa

from config import Config
from logger_setup import PipelineLogger


class PitchAnalyzer:
    """
    Performs pitch (F0) and volume variability analysis on an audio file
    using librosa. This is local signal processing — no Azure service involved.
    """

    # Human speech pitch range for PYIN detection
    FMIN_NOTE = "C2"  # ~65 Hz
    FMAX_NOTE = "C7"  # ~2093 Hz

    def __init__(self, config: Config, logger: PipelineLogger):
        self.config = config
        self.logger = logger

    def analyze(self, wav_file_path: Path) -> dict:
        """
        Loads the audio file and computes pitch and volume variability metrics.
        Returns a dict of computed pitch metrics.
        """
        self.logger.step(f"Analyzing pitch and tone: {wav_file_path.name}")

        y, sr = librosa.load(str(wav_file_path), sr=None)

        pitch_metrics = self._analyze_pitch(y, sr)
        volume_metrics = self._analyze_volume(y)

        metrics = {**pitch_metrics, **volume_metrics}

        self.logger.info(
            f"  Mean pitch: {metrics.get('mean_pitch_hz', 'N/A')} Hz, "
            f"Pitch CV: {metrics.get('pitch_cv_percent', 'N/A')}%, "
            f"Volume CV: {metrics.get('volume_cv_percent', 'N/A')}%"
        )

        return metrics

    def _analyze_pitch(self, y: np.ndarray, sr: int) -> dict:
        """Extracts F0 (pitch) statistics using the PYIN algorithm."""
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y,
            fmin=librosa.note_to_hz(self.FMIN_NOTE),
            fmax=librosa.note_to_hz(self.FMAX_NOTE),
            sr=sr
        )

        voiced_f0 = f0[~np.isnan(f0)]

        if len(voiced_f0) == 0:
            self.logger.warning("  No pitch detected in audio — check recording quality.")
            return {
                "mean_pitch_hz": 0.0,
                "std_pitch_hz": 0.0,
                "pitch_range_hz": 0.0,
                "pitch_cv_percent": 0.0
            }

        mean_pitch = float(np.mean(voiced_f0))
        std_pitch = float(np.std(voiced_f0))
        min_pitch = float(np.min(voiced_f0))
        max_pitch = float(np.max(voiced_f0))
        pitch_range = max_pitch - min_pitch
        pitch_cv = (std_pitch / mean_pitch) * 100 if mean_pitch > 0 else 0

        return {
            "mean_pitch_hz": round(mean_pitch, 1),
            "std_pitch_hz": round(std_pitch, 1),
            "pitch_range_hz": round(pitch_range, 1),
            "pitch_cv_percent": round(pitch_cv, 1)
        }

    def _analyze_volume(self, y: np.ndarray) -> dict:
        """Extracts RMS energy (volume) statistics."""
        rms = librosa.feature.rms(y=y)[0]
        mean_volume = float(np.mean(rms))
        std_volume = float(np.std(rms))
        volume_cv = (std_volume / mean_volume) * 100 if mean_volume > 0 else 0

        return {
            "mean_volume": round(mean_volume, 4),
            "volume_cv_percent": round(volume_cv, 1)
        }

    def save_metrics(self, metrics: dict, base_filename: str) -> Path:
        """Saves the pitch/volume metrics dict as JSON in /json_output."""
        json_path = self.config.json_output_folder / f"{base_filename}_pitch_metrics.json"

        with open(json_path, "w") as f:
            json.dump(metrics, f, indent=2)

        self.logger.info(f"  Pitch metrics saved to: {json_path}")
        return json_path
    
    