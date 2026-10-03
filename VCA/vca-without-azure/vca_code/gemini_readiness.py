# File: Repo/VCA/vca-without-azure/vca_code/gemini_readiness.py
# This module checks the readiness of the Gemini API and its dependencies before running the pipeline.
# Details:
#  - Creates the Gemini Client once and stores it on self.client — reused later by Transcriber
#  - Makes a genuinely minimal API call (a one-word response) purely to confirm the key/model combination works
#  - check_all() method: list of checks -> pass/fail pattern

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

# Flexible import handling for Config and PipelineLogger
try:
    from vca_code.config import Config
    from vca_code.logger_setup import PipelineLogger
except ImportError:
    try:
        from config import Config
        from logger_setup import PipelineLogger
    except ImportError:
        from app.services.config import Config
        from app.services.logger_setup import PipelineLogger


class GeminiReadinessChecker:
    """
    Verifies that the Gemini API is reachable and the API key is valid
    before the pipeline proceeds.
    """

    def __init__(self, config: Config, logger: PipelineLogger):
        self.config = config
        self.logger = logger
        self.client = None

    def check_all(self) -> bool:
        """Runs all readiness checks. Returns True only if everything passes."""
        self.logger.step("Checking Gemini API readiness")

        checks = [
            ("Gemini API key validity", self._check_gemini_api),
        ]

        for check_name, check_func in checks:
            try:
                check_func()
                self.logger.info(f"   ✓ {check_name}: OK")
            except Exception as e:
                # Re-raise rather than returning False. The caller's retry logic
                # inspects the exception to tell a transient rate limit apart from
                # a real failure; swallowing it here hid the cause and turned every
                # rate limit into a generic 500.
                self.logger.error(f"   ✗ {check_name}: FAILED — {str(e)}")
                raise

        self.logger.info("All Gemini readiness checks passed.")
        return True

    def _check_gemini_api(self):
        """
        Confirms the Gemini API key is valid by making a minimal, low-cost
        text generation call.
        """
        self.client = genai.Client(api_key=self.config.gemini_api_key)

        response = self.client.models.generate_content(
            model=self.config.gemini_model,
            contents="Reply with exactly one word: OK",
            config=types.GenerateContentConfig(
                temperature=0.0
            )
        )

        if not response or not response.text:
            raise RuntimeError("Gemini API returned an empty response.")