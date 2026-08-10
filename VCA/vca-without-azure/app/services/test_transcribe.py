# File: Repo/VCA/vca-without-azure/vca_code/test_transcribe.py
# This script tests the Transcriber class by transcribing a sample audio file.

from google import genai
from config import Config
from logger_setup import PipelineLogger
from transcription import Transcriber

cfg = Config()
logger = PipelineLogger(log_folder=cfg.log_folder, total_steps=8)
client = genai.Client(api_key=cfg.gemini_api_key)

transcriber = Transcriber(cfg, logger, client)

wav_file = cfg.audio_input_folder / "array_vs_linkedlist_1.wav"
base_name = wav_file.stem

transcript_text, segments = transcriber.transcribe(wav_file)
transcriber.save_transcript(transcript_text, base_name)
transcriber.save_segments(segments, base_name)

print(f"\nFull transcript:\n{transcript_text}")
print(f"\nSegments found: {len(segments)}")