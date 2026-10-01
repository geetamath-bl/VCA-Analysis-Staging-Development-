import os
import sys
import math
import time
import uuid
import shutil
import traceback
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from google import genai
from google.genai.errors import APIError

# Resolve path for vca_code modules
BASE_DIR = Path(__file__).resolve().parent.parent
vca_code_path = BASE_DIR / "vca_code"
if str(vca_code_path) not in sys.path:
    sys.path.insert(0, str(vca_code_path))

from config import Config
from logger_setup import PipelineLogger
from gemini_readiness import GeminiReadinessChecker
from audio_utils import AudioFileHandler
from transcription import Transcriber
from metrics_calculator import MetricsCalculator
from pitch_analyzer import PitchAnalyzer
from vocab_grammar_analyzer import VocabGrammarAnalyzer
from scorer import VCAScorer

router = APIRouter(
    prefix="/vca",
    tags=["VCA"]
)

# Global Instances
IS_VERCEL = bool(os.environ.get("VERCEL"))
config = Config()
logger = PipelineLogger(log_folder=config.log_folder, total_steps=8)

# Cached Readiness Client (Prevents wasting API quota on every request)
CACHED_GEMINI_CLIENT = None


def is_rate_limit_error(api_err: APIError) -> bool:
    return api_err.code == 429 or api_err.status == "RESOURCE_EXHAUSTED"


def get_retry_after_seconds(api_err: APIError, default: int = 60) -> int:
    """Reads Gemini's suggested retry delay (e.g. "23s") from the error details."""
    try:
        for detail in api_err.details["error"]["details"]:
            retry_delay = detail.get("retryDelay")
            if retry_delay:
                return max(1, math.ceil(float(retry_delay.rstrip("s"))))
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    return default


def gemini_error_to_http(api_err: APIError) -> HTTPException:
    """Maps a Gemini APIError to the HTTP error returned to the client."""
    if is_rate_limit_error(api_err):
        retry_after = get_retry_after_seconds(api_err)
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Gemini API rate limit reached. Please wait {retry_after} seconds and try again.",
            headers={"Retry-After": str(retry_after)}
        )
    return HTTPException(status_code=500, detail=f"Gemini API Error ({api_err.code}): {api_err.message}")


def get_gemini_client():
    """
    Executes CTO's GeminiReadinessChecker and caches the client instance.
    Retries transient failures (network errors, Gemini 5xx). Rate limits and
    other client errors (bad key, unknown model) are raised immediately with
    their real cause, since retrying them only spends more quota.
    """
    global CACHED_GEMINI_CLIENT

    if CACHED_GEMINI_CLIENT is not None:
        return CACHED_GEMINI_CLIENT

    readiness_checker = GeminiReadinessChecker(config, logger)
    max_retries = 3
    retry_delays = [5, 10]  # Delays in seconds between retries

    for attempt in range(max_retries):
        logger.info(f"Initializing Gemini Client (Attempt {attempt + 1}/{max_retries})...")
        if readiness_checker.check_all():
            CACHED_GEMINI_CLIENT = readiness_checker.client
            return CACHED_GEMINI_CLIENT

        error = readiness_checker.last_error
        if isinstance(error, APIError) and error.code is not None and error.code < 500:
            raise error

        if attempt < max_retries - 1:
            sleep_time = retry_delays[attempt]
            logger.warning(f"Readiness check failed ({error}). Retrying in {sleep_time}s...")
            time.sleep(sleep_time)

    error = readiness_checker.last_error
    if isinstance(error, APIError):
        raise error
    raise RuntimeError(f"Gemini readiness check failed after {max_retries} attempts: {error}")


@router.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """
    Upload an audio file to analyze communication skills and receive scores.
    """
    logger.info("=" * 70)
    logger.info("VCA Analyze API Called")
    logger.info("=" * 70)

    # Every file this request creates is tracked here and removed at the end
    request_files: list[Path] = []   # uploaded + converted audio
    output_files: list[Path] = []    # transcript and JSON reports
    original_filename = Path(file.filename or "audio.wav").name

    try:
        # 1. Save uploaded file under a unique name, so concurrent uploads
        #    with the same filename never overwrite each other
        try:
            uploaded_path = config.audio_input_folder / f"{uuid.uuid4().hex[:8]}_{original_filename}"
            request_files.append(uploaded_path)
            with open(uploaded_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            if uploaded_path.stat().st_size == 0:
                raise ValueError("The uploaded file is empty.")

            audio_handler = AudioFileHandler(logger)
            wav_path = audio_handler.prepare_audio_file(uploaded_path)
            request_files.append(wav_path)
            base_filename = wav_path.stem
            logger.info(f"Audio Ready: {wav_path.name}")

        except Exception as e:
            logger.error(f"Audio Preparation Failed: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=400, detail=f"Audio Preparation Error: {str(e)}")

        # 2. Gemini Readiness Check (With Client Caching and Retry Logic)
        try:
            client = get_gemini_client()
        except APIError as api_err:
            logger.error(f"Gemini API Error during readiness check: {api_err}")
            traceback.print_exc()
            raise gemini_error_to_http(api_err)
        except Exception as e:
            logger.error(f"Gemini Initialization Failed: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Gemini Readiness Failed: {str(e)}")

        # 3. Process Audio Analysis Pipeline
        try:
            logger.info("Starting Audio Analysis Pipeline...")

            # Step 3a: Transcribe
            transcriber = Transcriber(config, logger, client)
            transcript_text, segments = transcriber.transcribe(wav_path)
            output_files.append(transcriber.save_transcript(transcript_text, base_filename))
            output_files.append(transcriber.save_segments(segments, base_filename))

            # Step 3b: Pace, Fluency, Fillers
            metrics_calc = MetricsCalculator(config, logger)
            metrics = metrics_calc.compute_metrics(transcript_text, wav_path)
            output_files.append(metrics_calc.save_metrics(metrics, base_filename))

            # Step 3c: Expressiveness / Pitch
            pitch_calc = PitchAnalyzer(config, logger)
            pitch_metrics = pitch_calc.analyze(wav_path)
            output_files.append(pitch_calc.save_metrics(pitch_metrics, base_filename))

            # Step 3d: Vocab & Grammar
            vocab_calc = VocabGrammarAnalyzer(config, logger)
            vocab_metrics = vocab_calc.analyze(transcript_text)
            output_files.append(vocab_calc.save_metrics(vocab_metrics, base_filename))
            vocab_calc.close()

            # Step 3e: Score Computation
            scorer = VCAScorer(config, logger)
            score_report = scorer.compute_score(metrics, pitch_metrics, vocab_metrics)
            output_files.append(scorer.save_report(score_report, base_filename))

            logger.info("Analysis Completed Successfully.")

            return {
                "status": "success",
                "filename": original_filename,
                "report": {
                    "pace_score": score_report.get("pace_score"),
                    "fluency_score": score_report.get("fluency_score"),
                    "filler_score": score_report.get("filler_score"),
                    "expressiveness_score": score_report.get("expressiveness_score"),
                    "vocab_grammar_score": score_report.get("vocab_grammar_score"),
                    "overall_score": score_report.get("overall_score"),
                    "rating": score_report.get("rating")
                }
            }

        except APIError as api_err:
            logger.error(f"VCA Pipeline Gemini API Error: {api_err}")
            traceback.print_exc()
            raise gemini_error_to_http(api_err)

        except Exception as e:
            logger.error(f"VCA Pipeline Failed: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Uploaded and converted audio are always removed. Transcripts and JSON
        # reports are kept locally for inspection, but removed on Vercel, where
        # nobody can read them and they would only pile up in /tmp.
        logger.info("Cleaning temporary request files...")
        files_to_remove = request_files + (output_files if IS_VERCEL else [])
        for path in files_to_remove:
            try:
                path.unlink(missing_ok=True)
            except Exception as cleanup_err:
                logger.warning(f"Could not remove {path.name}: {cleanup_err}")
        logger.info("=" * 70)
        logger.info("Request Completed")
        logger.info("=" * 70)
