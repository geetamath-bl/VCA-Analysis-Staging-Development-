import json
from pathlib import Path
from google import genai

from config import Config
from logger_setup import PipelineLogger
from transcription_prompt import TRANSCRIPTION_PROMPT


class Transcriber:
    """
    Handles the transcription of audio files using the Gemini API.
    """

    def __init__(self, config: Config, logger: PipelineLogger, client: genai.Client):
        self.config = config
        self.logger = logger
        self.client = client  # reused from GeminiReadinessChecker

    def transcribe(self, wav_file_path: Path) -> tuple[str, list]:
        """
        Uploads the audio file to Gemini and requests a transcript.
        Returns a tuple of (full_transcript_text, list_of_segment_dicts).
        """
        self.logger.step(f"Transcribing audio file via Gemini: {wav_file_path.name}")

        self.logger.info("  Uploading audio file to Gemini...")
        uploaded_file = self.client.files.upload(file=str(wav_file_path))

        self.logger.info("  Requesting transcription...")
        response = self.client.models.generate_content(
            model=self.config.gemini_model,
            contents=[uploaded_file, TRANSCRIPTION_PROMPT]
        )

        full_transcript, segments = self._parse_response(response.text)

        if not full_transcript.strip():
            self.logger.warning("  No speech was recognized in this audio file.")

        self.logger.info(f"  Transcription complete. Transcript length: {len(full_transcript.split())} words")
        return full_transcript, segments

    def _parse_response(self, response_text: str) -> tuple[str, list]:
        """
        Parses Gemini's JSON response. Falls back gracefully if the model
        didn't return clean JSON (e.g., wrapped in markdown code fences).
        """
        cleaned = response_text.strip()

        # Gemini sometimes wraps JSON in ```json ... ``` fences despite instructions
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            data = json.loads(cleaned)
            full_transcript = data.get("full_transcript", "")
            segments = data.get("segments", [])
            return full_transcript, segments
        except json.JSONDecodeError:
            self.logger.warning(
                "  Could not parse Gemini response as JSON — falling back to raw text as transcript."
            )
            return response_text.strip(), []

    def save_transcript(self, transcript_text: str, base_filename: str) -> Path:
        """Saves the full transcript to a .txt file in the /transcript folder."""
        transcript_path = self.config.transcript_folder / f"{base_filename}_transcript.txt"

        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)

        self.logger.info(f"  Transcript saved to: {transcript_path}")
        return transcript_path

    def save_segments(self, segments: list, base_filename: str) -> Path:
        """Saves the segment-level timestamp data (if available) as JSON."""
        json_path = self.config.json_output_folder / f"{base_filename}_segments.json"

        with open(json_path, "w") as f:
            json.dump(segments, f, indent=2)

        self.logger.info(f"  Segments saved to: {json_path}")
        return json_path