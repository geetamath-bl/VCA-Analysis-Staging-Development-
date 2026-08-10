import tempfile
import shutil
import json
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.services.config import Config
from app.services.logger_setup import PipelineLogger
from app.services.gemini_readiness import GeminiReadinessChecker
from app.services.audio_utils import AudioFileHandler
from app.services.transcription import Transcriber
from app.services.metrics_calculator import MetricsCalculator
from app.services.pitch_analyzer import PitchAnalyzer
from app.services.vocab_grammar_analyzer import VocabGrammarAnalyzer
from app.services.scorer import VCAScorer

router = APIRouter()
TOTAL_STEPS = 8

@router.post("/vca/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    config = Config()
    logger = PipelineLogger(
        log_folder=config.log_folder,
        total_steps=TOTAL_STEPS
    )

    temp_file_path = None
    vocab_analyzer = None

    try:
        logger.info("=" * 70)
        logger.info("[STEP 1: API ROUTE] Request Received on POST /vca/analyze")
        logger.info(f"Uploaded Filename: {file.filename}")
        logger.info("=" * 70)

        # Validation
        if not file.filename:
            raise HTTPException(status_code=400, detail="Audio file is required")

        allowed_extensions = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {file_extension}"
            )

        temp_dir = Path(tempfile.gettempdir())
        temp_file_path = temp_dir / file.filename

        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Step 2: Audio Prep
        logger.step("Preparing audio file (WAV Conversion)")
        audio_handler = AudioFileHandler(logger)
        wav_path = audio_handler.prepare_audio_file(temp_file_path)
        base_filename = wav_path.stem

        # Step 3: Readiness Check
        logger.step("Checking Gemini API readiness")
        readiness_checker = GeminiReadinessChecker(config, logger)
        if not readiness_checker.check_all():
            raise HTTPException(status_code=500, detail="Gemini API readiness check failed")
        client = readiness_checker.client

        # Step 4: Transcription
        logger.step("Transcribing audio via Gemini")
        transcriber = Transcriber(config, logger, client)
        transcript_text, segments = transcriber.transcribe(wav_path)

        # Step 5: Pace/Fluency
        logger.step("Calculating pace, fluency, and filler metrics")
        metrics_calculator = MetricsCalculator(config, logger)
        metrics = metrics_calculator.compute_metrics(transcript_text, wav_path)
        logger.info(f"[METRICS CALCULATOR OUTPUT]: {json.dumps(metrics, indent=2)}")

        # Step 6: Pitch
        logger.step("Analyzing pitch and expressiveness")
        pitch_analyzer = PitchAnalyzer(config, logger)
        pitch_metrics = pitch_analyzer.analyze(wav_path)
        logger.info(f" [PITCH ANALYZER OUTPUT]: {json.dumps(pitch_metrics, indent=2)}")

        # Step 7: Vocab & Grammar
        logger.step("Analyzing vocabulary and grammar")
        vocab_analyzer = VocabGrammarAnalyzer(config, logger)
        vocab_metrics = vocab_analyzer.analyze(transcript_text)
        logger.info(f"[VOCAB ANALYZER OUTPUT]: {json.dumps(vocab_metrics, indent=2)}")

        # Step 8: Scorer
        logger.step("Computing final composite VCA score")
        scorer = VCAScorer(config, logger)
        score_report = scorer.compute_score(metrics, pitch_metrics, vocab_metrics)

        logger.info("=" * 70)
        logger.info(f" [SCORE REPORT COMPUTED]:\n{json.dumps(score_report, indent=2)}")
        logger.info("=" * 70)

        # Build response payload
        response = {
            "pace_score": score_report.get("pace_score"),
            "fluency_score": score_report.get("fluency_score"),
            "filler_score": score_report.get("filler_score"),
            "expressiveness_score": score_report.get("expressiveness_score"),
            "vocab_grammar_score": score_report.get("vocab_grammar_score"),
            "overall_score": score_report.get("overall_score"),
            "rating": score_report.get("rating")
        }

        logger.info(f"[FINAL API PAYLOAD SENT TO FRONTEND]:\n{json.dumps(response, indent=2)}")
        return JSONResponse(status_code=200, content=response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"VCA API pipeline failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"VCA analysis failed: {str(e)}")
    finally:
        if temp_file_path is not None and temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception:
                pass