import sys
from pathlib import Path

# Add project root and module folder dynamically to Python import path
_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from google import genai

# Import handling supporting both package execution and direct module execution
try:
    from vca_code.config import Config
    from vca_code.logger_setup import PipelineLogger
    from vca_code.gemini_readiness import GeminiReadinessChecker
    from vca_code.audio_utils import AudioFileHandler
    from vca_code.transcription import Transcriber
    from vca_code.metrics_calculator import MetricsCalculator
    from vca_code.pitch_analyzer import PitchAnalyzer
    from vca_code.vocab_grammar_analyzer import VocabGrammarAnalyzer
    from vca_code.scorer import VCAScorer
except ImportError:
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


def main():
    config = Config()
    logger = PipelineLogger(log_folder=config.log_folder, total_steps=TOTAL_STEPS)

    logger.info("=== Verbal Communication Ability (VCA) Pipeline Started (No-Azure / Gemini variant) ===")

    try:
        # --- Step 1: Gemini readiness check ---
        readiness_checker = GeminiReadinessChecker(config, logger)
        if not readiness_checker.check_all():
            logger.error("Gemini readiness check failed. Exiting pipeline.")
            sys.exit(1)

        client = readiness_checker.client  # reuse the same authenticated Gemini client

        # --- Step 2: Take audio file input ---
        logger.step("Taking audio file input")
        input_filename = input(
            f"Enter the audio file name (must be in '{config.audio_input_folder}'): "
        ).strip()
        input_path = config.audio_input_folder / input_filename

        # --- Step 3: Check extension / convert to WAV if needed ---
        audio_handler = AudioFileHandler(logger)
        wav_path = audio_handler.prepare_audio_file(input_path)
        base_filename = wav_path.stem

        # --- Step 4: Transcribe via Gemini ---
        transcriber = Transcriber(config, logger, client)
        transcript_text, segments = transcriber.transcribe(wav_path)
        transcriber.save_transcript(transcript_text, base_filename)
        transcriber.save_segments(segments, base_filename)

        # --- Step 5: Pace / fluency / filler metrics (silence-detection based) ---
        metrics_calculator = MetricsCalculator(config, logger)
        metrics = metrics_calculator.compute_metrics(transcript_text, wav_path)
        metrics_calculator.save_metrics(metrics, base_filename)

        # --- Step 6: Pitch/tone analysis ---
        pitch_analyzer = PitchAnalyzer(config, logger)
        pitch_metrics = pitch_analyzer.analyze(wav_path)
        pitch_analyzer.save_metrics(pitch_metrics, base_filename)

        # --- Step 7: Vocabulary/grammar analysis ---
        vocab_analyzer = VocabGrammarAnalyzer(config, logger)
        vocab_metrics = vocab_analyzer.analyze(transcript_text)
        vocab_analyzer.save_metrics(vocab_metrics, base_filename)
        vocab_analyzer.close()

        # --- Step 8: Compute composite VCA score ---
        scorer = VCAScorer(config, logger)
        score_report = scorer.compute_score(metrics, pitch_metrics, vocab_metrics)
        scorer.save_report(score_report, base_filename)

        # --- Final summary ---
        logger.info("=== VCA Pipeline (No-Azure) Completed Successfully ===")
        logger.info(f"Overall VCA Score: {score_report['overall_score']}/100 "
                    f"-> {score_report['rating']}")
        logger.info(f"All outputs saved under: {config.project_root}")

        print("\n" + "=" * 50)
        print("FINAL VERBAL COMMUNICATION ABILITY (VCA) REPORT")
        print("(No-Azure / Gemini variant)")
        print("=" * 50)
        for key, value in score_report.items():
            print(f"{key}: {value}")

    except Exception as e:
        logger.error(f"Pipeline failed with an unexpected error: {str(e)}")
        raise


if __name__ == "__main__":
    main()