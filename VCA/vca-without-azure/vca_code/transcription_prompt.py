# File: Repo/VCA/vca-without-azure/vca_code/transcription_prompt.py
# This module contains prompt templates for Gemini-based audio transcription.

"""
Prompt templates for Gemini-based audio transcription.
"""

TRANSCRIPTION_PROMPT = """
Transcribe this audio recording completely and accurately, word for word,
including any filler words like "um", "uh", "like" if clearly audible.

Return your response as valid JSON only, no other text, in this exact format:
{
  "full_transcript": "the complete transcript as a single string",
  "segments": [
    {"start_time": "MM:SS", "end_time": "MM:SS", "text": "segment text"}
  ]
}
"""