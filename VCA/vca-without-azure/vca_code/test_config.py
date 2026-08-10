# File: Repo/VCA/vca-without-azure/vca_code/test_config.py
# This file is a simple test script to verify that the configuration settings 
#  are loaded correctly from the .env file.

from config import Config

cfg = Config()
print("Gemini model:", cfg.gemini_model)
print("Audio input folder:", cfg.audio_input_folder)