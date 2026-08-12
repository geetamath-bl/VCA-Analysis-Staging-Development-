# File: vca_code/audio_utils.py

import subprocess
import shutil
from pathlib import Path

from logger_setup import PipelineLogger


class AudioFileHandler:
    """
    Handles audio file input validation and conversion.

    If FFmpeg is available, non-WAV files can be converted locally.
    If FFmpeg is not available (for example, on Vercel), the backend
    can still process WAV files directly.
    """

    TARGET_SAMPLE_RATE = 16000
    TARGET_CHANNELS = 1

    def __init__(self, logger: PipelineLogger):
        self.logger = logger

        # Do not fail during application startup/deployment if FFmpeg
        # is unavailable. Vercel does not provide FFmpeg by default.
        self.ffmpeg_path = shutil.which("ffmpeg")

        if self.ffmpeg_path:
            self.logger.info(f"FFmpeg found: {self.ffmpeg_path}")
        else:
            self.logger.info(
                "FFmpeg not found. WAV files will be processed directly."
            )

    def prepare_audio_file(self, input_path: Path) -> Path:
        """
        Validates the input audio file and converts it to WAV if necessary.

        WAV files can be processed without FFmpeg.
        Non-WAV files require FFmpeg.
        """

        self.logger.step(f"Checking audio file: {input_path.name}")

        if not input_path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {input_path}"
            )

        # WAV does not require FFmpeg.
        if input_path.suffix.lower() == ".wav":
            self.logger.info(
                "  File is already .wav — no FFmpeg conversion needed."
            )
            return input_path

        # Non-WAV files require FFmpeg.
        if not self.ffmpeg_path:
            raise EnvironmentError(
                f"FFmpeg is not available on this server. "
                f"Please upload a WAV file. Received: {input_path.suffix}"
            )

        self.logger.info(
            f"  File extension is '{input_path.suffix}' — "
            "conversion to .wav required."
        )

        return self._convert_to_wav(input_path)

    def _convert_to_wav(self, input_path: Path) -> Path:
        """
        Converts the given audio file to:
        - 16kHz
        - 16-bit
        - mono
        - PCM WAV

        using FFmpeg.
        """

        if not self.ffmpeg_path:
            raise EnvironmentError(
                "FFmpeg is not available. Cannot convert audio."
            )

        output_path = input_path.with_suffix(".wav")

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(input_path),
            "-ar",
            str(self.TARGET_SAMPLE_RATE),
            "-ac",
            str(self.TARGET_CHANNELS),
            "-sample_fmt",
            "s16",
            str(output_path),
        ]

        self.logger.info(
            f"  Running FFmpeg conversion: "
            f"{input_path.name} -> {output_path.name}"
        )

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            self.logger.error(
                f"  FFmpeg conversion failed: {result.stderr}"
            )

            raise RuntimeError(
                f"FFmpeg conversion failed for {input_path}: "
                f"{result.stderr}"
            )

        self.logger.info(
            f"  Conversion successful: {output_path}"
        )

        return output_path