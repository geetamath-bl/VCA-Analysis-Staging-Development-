import sys
import time
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
config = Config()
logger = PipelineLogger(log_folder=config.log_folder, total_steps=8)

# Cached Readiness Client (Prevents wasting API quota on every request)
CACHED_GEMINI_CLIENT = None


def get_gemini_client():
    """
    Executes CTO's GeminiReadinessChecker and caches the client instance.
    Includes retry logic if Google API limits are temporarily hit.
    """
    global CACHED_GEMINI_CLIENT

    if CACHED_GEMINI_CLIENT is not None:
        return CACHED_GEMINI_CLIENT

    readiness_checker = GeminiReadinessChecker(config, logger)
    max_retries = 3
    retry_delays = [5, 10]  # Delays in seconds between retries

    for attempt in range(max_retries):
        try:
            logger.info(f"Initializing Gemini Client (Attempt {attempt + 1}/{max_retries})...")
            if readiness_checker.check_all():
                CACHED_GEMINI_CLIENT = readiness_checker.client
                return CACHED_GEMINI_CLIENT
        except APIError as api_err:
            if "429" in str(api_err) or "RESOURCE_EXHAUSTED" in str(api_err):
                if attempt < max_retries - 1:
                    sleep_time = retry_delays[attempt]
                    logger.warning(f"Rate limit hit during readiness check. Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue
            raise api_err
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = retry_delays[attempt]
                logger.warning(f"Readiness check failed ({e}). Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
                continue
            raise e

    raise RuntimeError("Gemini readiness check failed after maximum retries.")


@router.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """
    Upload an audio file to analyze communication skills and receive scores.
    """
    logger.info("=" * 70)
    logger.info("VCA Analyze API Called")
    logger.info("=" * 70)

    uploaded_path: Path | None = None

    # 1. Save uploaded file to temp path
    try:
        uploaded_path = config.audio_input_folder / file.filename
        with open(uploaded_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        audio_handler = AudioFileHandler(logger)
        wav_path = audio_handler.prepare_audio_file(uploaded_path)
        base_filename = wav_path.stem
        logger.info(f"Audio Ready: {wav_path.name}")

    except Exception as e:
        logger.error(f"Audio Preparation Failed: {e}")
        traceback.print_exc()
        if uploaded_path and uploaded_path.exists():
            uploaded_path.unlink()
        raise HTTPException(status_code=400, detail=f"Audio Preparation Error: {str(e)}")

    # 2. Gemini Readiness Check (With Client Caching and Retry Logic)
    try:
        client = get_gemini_client()
    except APIError as api_err:
        logger.error(f"Gemini API Error during readiness check: {api_err}")
        traceback.print_exc()
        if uploaded_path and uploaded_path.exists():
            uploaded_path.unlink()

        if "429" in str(api_err) or "RESOURCE_EXHAUSTED" in str(api_err):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Gemini API rate limit reached. Please wait a minute before analyzing another file."
            )
        raise HTTPException(status_code=500, detail=f"Gemini API Error: {str(api_err)}")
    except Exception as e:
        logger.error(f"Gemini Initialization Failed: {e}")
        traceback.print_exc()
        if uploaded_path and uploaded_path.exists():
            uploaded_path.unlink()
        raise HTTPException(status_code=500, detail=f"Gemini Readiness Failed: {str(e)}")

    # 3. Process Audio Analysis Pipeline
    try:
        logger.info("Starting Audio Analysis Pipeline...")

        # Step 3a: Transcribe
        transcriber = Transcriber(config, logger, client)
        transcript_text, segments = transcriber.transcribe(wav_path)
        transcriber.save_transcript(transcript_text, base_filename)
        transcriber.save_segments(segments, base_filename)

        # Step 3b: Pace, Fluency, Fillers
        metrics_calc = MetricsCalculator(config, logger)
        metrics = metrics_calc.compute_metrics(transcript_text, wav_path)
        metrics_calc.save_metrics(metrics, base_filename)

        # Step 3c: Expressiveness / Pitch
        pitch_calc = PitchAnalyzer(config, logger)
        pitch_metrics = pitch_calc.analyze(wav_path)
        pitch_calc.save_metrics(pitch_metrics, base_filename)

        # Step 3d: Vocab & Grammar
        vocab_calc = VocabGrammarAnalyzer(config, logger)
        vocab_metrics = vocab_calc.analyze(transcript_text)
        vocab_calc.save_metrics(vocab_metrics, base_filename)
        vocab_calc.close()

        # Step 3e: Score Computation
        scorer = VCAScorer(config, logger)
        score_report = scorer.compute_score(metrics, pitch_metrics, vocab_metrics)
        scorer.save_report(score_report, base_filename)

        logger.info("Analysis Completed Successfully.")

        return {
            "status": "success",
            "filename": file.filename,
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
        if "429" in str(api_err) or "RESOURCE_EXHAUSTED" in str(api_err):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Gemini API rate limit exceeded during analysis. Please wait ~30 seconds and retry."
            )
        raise HTTPException(status_code=500, detail=f"Gemini API Error: {str(api_err)}")

    except Exception as e:
        logger.error(f"VCA Pipeline Failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        logger.info("Cleaning Temporary Input File...")
        if uploaded_path and uploaded_path.exists():
            try:
                uploaded_path.unlink()
            except Exception:
                pass
        logger.info("=" * 70)
        logger.info("Request Completed")
        logger.info("=" * 70)