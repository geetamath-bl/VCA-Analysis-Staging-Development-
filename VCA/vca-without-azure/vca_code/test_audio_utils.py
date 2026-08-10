from config import Config
from logger_setup import PipelineLogger
from audio_utils import AudioFileHandler

cfg = Config()
logger = PipelineLogger(log_folder=cfg.log_folder, total_steps=8)

handler = AudioFileHandler(logger)

test_file = cfg.audio_input_folder /"array_vs_linkedlist_1.m4a"
wav_path = handler.prepare_audio_file(test_file)

print(f"\nReady-to-use WAV file path: {wav_path}")