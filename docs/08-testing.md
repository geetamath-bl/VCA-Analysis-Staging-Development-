# 8. Testing

---

## 8.1 What exists today

Nine files named `test_*.py` live in `vca_code/`. Despite the naming, they are
**not** pytest tests — they are top-level manual smoke scripts that execute on
import, print to stdout, and contain no assertions. Running `pytest` against the
folder would execute all nine at collection time, making real Gemini and
LanguageTool calls as a side effect.

| Script | Lines | Exercises | Needs |
|---|---|---|---|
| `test_config.py` | 8 | `.env` loading, folder derivation | `.env` |
| `test_logger.py` | 11 | Console + file logging, `step()` | `.env` |
| `test_readiness.py` | 15 | Gemini key and model validity | `.env`, network |
| `test_audio_utils.py` | 12 | FFmpeg conversion | sample `.m4a`, FFmpeg |
| `test_transcribe.py` | 22 | Gemini transcription and parsing | sample `.wav`, network |
| `test_metrics.py` | 22 | Pace, pause, filler computation | sample `.wav` + transcript |
| `test_pitch_analyzer.py` | 20 | PYIN pitch, RMS volume | sample `.wav` |
| `test_vocab_grammar.py` | 20 | TTR, LanguageTool errors | transcript, network |
| `test_scorer.py` | 25 | Rubric and composite score | the three metric JSON files |

They encode a **sequential dependency chain** — each stage consumes the previous
stage's output file — and every one references the same fixture base name,
`array_vs_linkedlist_1`:

```
test_audio_utils     .m4a ──────────────► audio_files/array_vs_linkedlist_1.wav
test_transcribe      .wav ──────────────► transcript/..._transcript.txt
                                          json_output/..._segments.json
test_metrics         .wav + transcript ─► json_output/..._metrics.json
test_pitch_analyzer  .wav ──────────────► json_output/..._pitch_metrics.json
test_vocab_grammar   transcript ────────► json_output/..._vocab_metrics.json
test_scorer          3 × metrics JSON ──► json_output/..._score_report.json
```

**The fixture is not in the repository.** `audio_files/` is gitignored, so
`array_vs_linkedlist_1.m4a` must be supplied locally. Without it, every script
from `test_audio_utils.py` onwards fails with `FileNotFoundError`.

Note also that `test_pitch_analyzer.py` saves with base name
`"array_vs_linkedlist_1_pitch_metrics"`, and `save_metrics` appends its own
`_pitch_metrics` suffix, producing
`array_vs_linkedlist_1_pitch_metrics_pitch_metrics.json`. `test_scorer.py`
reads `array_vs_linkedlist_1_pitch_metrics.json`, so running the chain as-is
leaves the scorer step unable to find its input. Passing
`"array_vs_linkedlist_1"` fixes it.

---

## 8.2 Running them

They use flat imports (`from config import Config`), so they must be run from
inside `vca_code/`:

```bash
cd VCA/vca-without-azure/vca_code

# No fixture needed:
python test_config.py
python test_logger.py
python test_readiness.py          # makes one real Gemini call

# Place your sample first:
#   cp your_sample.m4a ../audio_files/array_vs_linkedlist_1.m4a
python test_audio_utils.py        # needs FFmpeg
python test_transcribe.py         # real Gemini call, costs quota
python test_metrics.py
python test_pitch_analyzer.py
python test_vocab_grammar.py      # real LanguageTool call
python test_scorer.py
```

Run them in that order — later scripts read earlier ones' output.

### Full-chain convenience script

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/VCA/vca-without-azure/vca_code"
for t in config logger readiness audio_utils transcribe metrics \
         pitch_analyzer vocab_grammar scorer; do
  echo "═══ test_$t ═══"
  python "test_$t.py"
done
```

---

## 8.3 End-to-end check through the API

The most useful single test is the real request:

```bash
# Terminal 1
cd VCA/vca-without-azure/vca_code && python main.py

# Terminal 2
curl -s -X POST http://localhost:8000/vca/analyze \
  -F "file=@sample.wav" | python -m json.tool
```

Expect a `200` with seven score fields. Then check the artifacts and log:

```bash
ls -la VCA/vca-without-azure/json_output/
tail -40 VCA/vca-without-azure/log/vca_run_*.log
```

A healthy log shows the numbered steps in order:

```
[STEP 1/8] Checking audio file: sample.wav
[STEP 2/8] Checking Gemini API readiness
   ✓ Gemini API key validity: OK
[STEP 3/8] Transcribing audio file via Gemini: sample.wav
[STEP 4/8] Computing pace, pause, and filler word metrics
[STEP 5/8] Analyzing pitch and tone: sample.wav
[STEP 6/8] Analyzing vocabulary and grammar
[STEP 7/8] Computing composite Verbal Communication Ability (VCA) score
```

Step numbers climbing past `8/8` on later requests is expected — the logger is a
module-global with a cumulative counter.

### Browser path

1. Open `http://localhost:8000/`.
2. **Upload tab** — pick an MP3 or M4A, confirm the status banner shows the
   conversion, then the analysis, then results.
3. **Record tab** — record 30–60 seconds, confirm the timer, the preview player,
   the download link, and that analysis of the recording works.
4. Confirm the rating text and all five metric boxes populate.

---

## 8.4 What is not covered

| Gap | Why it matters |
|---|---|
| No assertions anywhere | A script that runs without crashing proves nothing about correctness |
| No pytest / CI | Nothing runs automatically on push |
| No mocking | Every run costs Gemini quota and hits LanguageTool |
| No scorer unit tests | The rubric is pure arithmetic — the cheapest, highest-value thing to test, and untested |
| No band-boundary tests | Off-by-one at 120/160 WPM, 2 %/5 % filler, 0.5/0.75 TTR would go unnoticed |
| No error-path tests | `400`, `429`, `500` mappings are unverified |
| No empty-transcript test | Silent audio currently returns a plausible-looking score (see [09-known-issues.md](09-known-issues.md)) |
| No fixtures committed | The chain cannot run on a clean clone |

---

## 8.5 Suggested test strategy

### Tier 1 — pure unit tests, no I/O

`VCAScorer` and the vocabulary/filler helpers are pure functions over numbers
and strings. They need no audio, no network and no API key, so they are fast,
deterministic and free. This is where to start.

```python
# tests/test_scorer_units.py
import pytest
from scorer import VCAScorer

@pytest.fixture
def scorer():
    return VCAScorer(config=None, logger=None)   # neither is touched by the
                                                 # scoring methods

@pytest.mark.parametrize("wpm,expected", [
    (119, 80), (120, 100), (160, 100), (161, 80),   # band boundaries
    (79, 40),  (201, 40),                            # extremes
])
def test_pace_bands(scorer, wpm, expected):
    assert scorer._score_pace(wpm) == expected

def test_long_pause_penalty_floors_at_zero(scorer):
    # base 100 (0 pauses/min) minus 10 × 12 long pauses must not go negative
    assert scorer._score_fluency(num_pauses=0, long_pauses=12,
                                 total_duration_sec=600) == 0

def test_expressiveness_floors_at_thirty(scorer):
    assert scorer._score_expressiveness(pitch_cv=0, volume_cv=0) >= 30

@pytest.mark.parametrize("score,label", [
    (85, "Excellent"), (84.9, "Good"), (70, "Good"),
    (69.9, "Fair"), (50, "Fair"), (49.9, "Needs Improvement"),
])
def test_rating_boundaries(scorer, score, label):
    assert scorer._rating_label(score) == label

def test_worked_example_composite(scorer):
    report = scorer.compute_score(
        metrics={"wpm": 134.8, "num_pauses": 19, "long_pauses": 1,
                 "total_duration_sec": 183.42, "filler_ratio": 2.2},
        pitch_metrics={"pitch_cv_percent": 22.4, "volume_cv_percent": 58.3},
        vocab_metrics={"ttr": 0.609, "errors_per_100_words": 3.4},
    )
    assert report["overall_score"] == 86.5
    assert report["rating"] == "Excellent"
```

That last case is the worked example from
[04-scoring-methodology.md §4.8](04-scoring-methodology.md#48-worked-example),
which makes the documentation and the test suite check each other.

### Tier 2 — unit tests with small synthetic audio

Generate deterministic WAV files with NumPy instead of committing fixtures:

```python
import numpy as np, soundfile as sf

def make_tone_with_gap(path, sr=16000):
    """1 s of 200 Hz tone, 2 s of silence, 1 s of tone → exactly one long pause."""
    t = np.linspace(0, 1, sr, endpoint=False)
    tone = 0.3 * np.sin(2 * np.pi * 200 * t)
    sf.write(path, np.concatenate([tone, np.zeros(2 * sr), tone]), sr)
```

This gives exact ground truth for pause detection (`num_pauses == 1`,
`long_pauses == 1`) and pitch (`mean_pitch_hz ≈ 200`), with no fixture files in
the repository.

### Tier 3 — API tests with mocked externals

```python
from fastapi.testclient import TestClient

def test_analyze_rejects_non_wav_without_ffmpeg(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    ...  # assert 400 and the message tells the caller to send WAV

def test_rate_limit_maps_to_429(monkeypatch):
    ...  # make the Gemini call raise a 429 APIError, assert 429 and the message
```

Patch `Transcriber.transcribe` and `VocabGrammarAnalyzer._check_grammar` so no
network call happens. This is where the `400` / `429` / `500` mappings and the
upload-cleanup guarantee get verified.

### Tier 4 — one live integration test

A single opt-in test (`@pytest.mark.integration`, skipped unless
`GEMINI_API_KEY` is present) that posts a real WAV and asserts the response
shape. Excluded from the default run so CI stays free and fast.

### Suggested layout

```
VCA/vca-without-azure/
├── tests/
│   ├── conftest.py              fixtures, synthetic audio generators
│   ├── test_scorer_units.py     Tier 1
│   ├── test_metrics_units.py    Tier 1 + 2
│   ├── test_pitch_units.py      Tier 2
│   ├── test_api.py              Tier 3
│   └── test_integration.py      Tier 4, opt-in
├── pytest.ini
└── vca_code/
    └── ... (the existing test_*.py scripts moved to scripts/smoke/ or renamed)
```

Renaming the current scripts to something outside the `test_*` glob — for
example `scripts/smoke/check_config.py` — is worth doing early. It stops pytest
from executing them at collection time, which is what makes a real test suite
possible in the first place.

```ini
# pytest.ini
[pytest]
testpaths = tests
markers =
    integration: hits real Gemini and LanguageTool APIs; needs GEMINI_API_KEY
addopts = -m "not integration"
```
