# File: wAzure/vca_code/audio_utils.py
# This module provides utilities for handling audio files, 
# including validation and conversion to a standard format 
#                         (16kHz, 16-bit, mono PCM WAV) using ffmpeg.

import subprocess
import shutil
from pathlib import Path

from logger_setup import PipelineLogger


class AudioFileHandler:
    """
    Handles audio file input validation and conversion.
    Ensures the pipeline always works with a proper
    16kHz, 16-bit, mono PCM WAV file, converting via ffmpeg if needed.
    """

    TARGET_SAMPLE_RATE = 16000
    TARGET_CHANNELS = 1

    def __init__(self, logger: PipelineLogger):
        self.logger = logger
        self._check_ffmpeg_available()

    def _check_ffmpeg_available(self):
        """Confirms ffmpeg is installed and reachable on PATH."""
        if shutil.which("ffmpeg") is None:
            raise EnvironmentError(
                "ffmpeg not found on PATH. Install it first (e.g., 'brew install ffmpeg' on window)."
            )

    def prepare_audio_file(self, input_path: Path) -> Path:
        """
        Validates the input audio file and converts it to WAV if necessary.
        Returns the path to a WAV file ready for downstream processing.
        """
        self.logger.step(f"Checking audio file: {input_path.name}")

        if not input_path.exists():
            raise FileNotFoundError(f"Audio file not found: {input_path}")

        if input_path.suffix.lower() == ".wav":
            self.logger.info(f"  File is already .wav — no conversion needed.")
            return input_path

        self.logger.info(f"  File extension is '{input_path.suffix}' — conversion to .wav required.")
        converted_path = self._convert_to_wav(input_path)
        return converted_path

    def _convert_to_wav(self, input_path: Path) -> Path:
        """
        Converts the given audio file to 16kHz, 16-bit, mono PCM WAV
        using ffmpeg. Saves the converted file alongside the original,
        with the same base name and a .wav extension.
        """
        output_path = input_path.with_suffix(".wav")

        cmd = [
            "ffmpeg",
            "-y",  # overwrite output file if it already exists
            "-i", str(input_path),
            "-ar", str(self.TARGET_SAMPLE_RATE),
            "-ac", str(self.TARGET_CHANNELS),
            "-sample_fmt", "s16",
            str(output_path)
        ]

        self.logger.info(f"  Running ffmpeg conversion: {input_path.name} -> {output_path.name}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.logger.error(f"  ffmpeg conversion failed: {result.stderr}")
            raise RuntimeError(f"ffmpeg conversion failed for {input_path}: {result.stderr}")

        self.logger.info(f"  Conversion successful: {output_path}")
        return output_path
    
