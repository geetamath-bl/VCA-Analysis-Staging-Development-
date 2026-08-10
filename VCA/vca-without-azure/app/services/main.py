# import sys
# from google import genai

# from config import Config
# from logger_setup import PipelineLogger
# from gemini_readiness import GeminiReadinessChecker
# from audio_utils import AudioFileHandler
# from transcription import Transcriber
# from metrics_calculator import MetricsCalculator
# from pitch_analyzer import PitchAnalyzer
# from vocab_grammar_analyzer import VocabGrammarAnalyzer
# from scorer import VCAScorer

# TOTAL_STEPS = 8


# def main():
#     config = Config()
#     logger = PipelineLogger(log_folder=config.log_folder, total_steps=TOTAL_STEPS)

#     logger.info("=== Verbal Communication Ability (VCA) Pipeline Started (No-Azure / Gemini variant) ===")

#     try:
#         # --- Step 1: Gemini readiness check ---
#         readiness_checker = GeminiReadinessChecker(config, logger)
#         if not readiness_checker.check_all():
#             logger.error("Gemini readiness check failed. Exiting pipeline.")
#             sys.exit(1)

#         client = readiness_checker.client  # reuse the same authenticated Gemini client

#         # --- Step 2: Take audio file input ---
#         logger.step("Taking audio file input")
#         input_filename = input(
#             f"Enter the audio file name (must be in '{config.audio_input_folder}'): "
#         ).strip()
#         input_path = config.audio_input_folder / input_filename

#         # --- Step 3: Check extension / convert to WAV if needed ---
#         audio_handler = AudioFileHandler(logger)
#         wav_path = audio_handler.prepare_audio_file(input_path)
#         base_filename = wav_path.stem

#         # --- Step 4: Transcribe via Gemini ---
#         transcriber = Transcriber(config, logger, client)
#         transcript_text, segments = transcriber.transcribe(wav_path)
#         transcriber.save_transcript(transcript_text, base_filename)
#         transcriber.save_segments(segments, base_filename)

#         # --- Step 5: Pace / fluency / filler metrics (silence-detection based) ---
#         metrics_calculator = MetricsCalculator(config, logger)
#         metrics = metrics_calculator.compute_metrics(transcript_text, wav_path)
#         metrics_calculator.save_metrics(metrics, base_filename)

#         # --- Step 6: Pitch/tone analysis ---
#         pitch_analyzer = PitchAnalyzer(config, logger)
#         pitch_metrics = pitch_analyzer.analyze(wav_path)
#         pitch_analyzer.save_metrics(pitch_metrics, base_filename)

#         # --- Step 7: Vocabulary/grammar analysis ---
#         vocab_analyzer = VocabGrammarAnalyzer(config, logger)
#         vocab_metrics = vocab_analyzer.analyze(transcript_text)
#         vocab_analyzer.save_metrics(vocab_metrics, base_filename)
#         vocab_analyzer.close()

#         # --- Step 8: Compute composite VCA score ---
#         scorer = VCAScorer(config, logger)
#         score_report = scorer.compute_score(metrics, pitch_metrics, vocab_metrics)
#         scorer.save_report(score_report, base_filename)

#         # --- Final summary ---
#         logger.info("=== VCA Pipeline (No-Azure) Completed Successfully ===")
#         logger.info(f"Overall VCA Score: {score_report['overall_score']}/100 "
#                      f"-> {score_report['rating']}")
#         logger.info(f"All outputs saved under: {config.project_root}")

#         print("\n" + "=" * 50)
#         print("FINAL VERBAL COMMUNICATION ABILITY (VCA) REPORT")
#         print("(No-Azure / Gemini variant)")
#         print("=" * 50)
#         for key, value in score_report.items():
#             print(f"{key}: {value}")

#     except Exception as e:
#         logger.error(f"Pipeline failed with an unexpected error: {str(e)}")
#         raise


# if __name__ == "__main__":
#     main()

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import shutil
from pathlib import Path

from config import Config
from logger_setup import PipelineLogger
from gemini_readiness import GeminiReadinessChecker
from audio_utils import AudioFileHandler
from transcription import Transcriber
from metrics_calculator import MetricsCalculator
from pitch_analyzer import PitchAnalyzer
from vocab_grammar_analyzer import VocabGrammarAnalyzer
from scorer import VCAScorer


TOTAL_STEPS = 8

app = FastAPI(
    title="VCA - Verbal Communication Ability API",
    description="VCA Audio Evaluation API",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "VCA API is running"
    }


@app.post("/vca/analyze")
async def analyze_audio(file: UploadFile = File(...)):

    config = Config()

    logger = PipelineLogger(
        log_folder=config.log_folder,
        total_steps=TOTAL_STEPS
    )

    temp_file_path = None
    vocab_analyzer = None

    try:
        logger.info("=== VCA API Pipeline Started ===")

        # ==========================================================
        # STEP 1: Validate uploaded file
        # ==========================================================

        logger.step("Validating uploaded audio file")

        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Audio file is required"
            )

        allowed_extensions = {
            ".wav",
            ".mp3",
            ".m4a",
            ".ogg",
            ".flac"
        }

        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported audio format: {file_extension}. "
                    f"Allowed formats: {', '.join(allowed_extensions)}"
                )
            )

        # ==========================================================
        # STEP 2: Save uploaded file temporarily
        # ==========================================================

        logger.step("Saving uploaded audio file")

        temp_dir = Path(tempfile.gettempdir())

        temp_file_path = temp_dir / file.filename

        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(
            f"Uploaded file saved temporarily at: {temp_file_path}"
        )

        # ==========================================================
        # STEP 3: Prepare audio / convert to WAV
        # ==========================================================

        logger.step("Preparing audio file")

        audio_handler = AudioFileHandler(logger)

        wav_path = audio_handler.prepare_audio_file(
            temp_file_path
        )

        base_filename = wav_path.stem

        logger.info(
            f"Audio prepared successfully: {wav_path}"
        )

        # ==========================================================
        # STEP 4: Gemini readiness check
        # ==========================================================

        logger.step("Checking Gemini readiness")

        readiness_checker = GeminiReadinessChecker(
            config,
            logger
        )

        if not readiness_checker.check_all():

            logger.error(
                "Gemini readiness check failed."
            )

            raise HTTPException(
                status_code=500,
                detail="Gemini readiness check failed"
            )

        client = readiness_checker.client

        # ==========================================================
        # STEP 5: Transcription
        # ==========================================================

        logger.step("Transcribing audio")

        transcriber = Transcriber(
            config,
            logger,
            client
        )

        transcript_text, segments = transcriber.transcribe(
            wav_path
        )

        transcriber.save_transcript(
            transcript_text,
            base_filename
        )

        transcriber.save_segments(
            segments,
            base_filename
        )

        # ==========================================================
        # STEP 6: Pace / Fluency / Filler metrics
        # ==========================================================

        logger.step(
            "Calculating pace, fluency and filler metrics"
        )

        metrics_calculator = MetricsCalculator(
            config,
            logger
        )

        metrics = metrics_calculator.compute_metrics(
            transcript_text,
            wav_path
        )

        metrics_calculator.save_metrics(
            metrics,
            base_filename
        )

        # ==========================================================
        # STEP 7: Pitch / Expressiveness
        # ==========================================================

        logger.step(
            "Analyzing pitch and expressiveness"
        )

        pitch_analyzer = PitchAnalyzer(
            config,
            logger
        )

        pitch_metrics = pitch_analyzer.analyze(
            wav_path
        )

        pitch_analyzer.save_metrics(
            pitch_metrics,
            base_filename
        )

        # ==========================================================
        # STEP 8: Vocabulary, Grammar and Final Score
        # ==========================================================

        logger.step(
            "Analyzing vocabulary, grammar and final score"
        )

        vocab_analyzer = VocabGrammarAnalyzer(
            config,
            logger
        )

        vocab_metrics = vocab_analyzer.analyze(
            transcript_text
        )

        vocab_analyzer.save_metrics(
            vocab_metrics,
            base_filename
        )

        vocab_analyzer.close()
        vocab_analyzer = None

        # ==========================================================
        # FINAL SCORE
        # ==========================================================

        scorer = VCAScorer(
            config,
            logger
        )

        score_report = scorer.compute_score(
            metrics,
            pitch_metrics,
            vocab_metrics
        )

        scorer.save_report(
            score_report,
            base_filename
        )

        logger.info(
            "=== VCA API Pipeline Completed Successfully ==="
        )

        logger.info(
            f"Overall VCA Score: "
            f"{score_report['overall_score']}/100 "
            f"-> {score_report['rating']}"
        )

        # ==========================================================
        # RETURN ONLY REQUIRED RESPONSE
        # ==========================================================

        response = {
            "pace_score": score_report.get("pace_score"),
            "fluency_score": score_report.get("fluency_score"),
            "filler_score": score_report.get("filler_score"),
            "expressiveness_score": score_report.get(
                "expressiveness_score"
            ),
            "vocab_grammar_score": score_report.get(
                "vocab_grammar_score"
            ),
            "overall_score": score_report.get(
                "overall_score"
            ),
            "rating": score_report.get("rating")
        }

        return JSONResponse(
            status_code=200,
            content=response
        )

    except HTTPException:
        raise

    except Exception as e:

        logger.error(
            f"VCA pipeline failed: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"VCA analysis failed: {str(e)}"
        )

    finally:

        # Close analyzer if something failed before normal close
        if vocab_analyzer is not None:
            try:
                vocab_analyzer.close()
            except Exception:
                pass

        # Remove temporary uploaded file
        if temp_file_path is not None:

            try:
                if temp_file_path.exists():
                    temp_file_path.unlink()

            except Exception:
                pass