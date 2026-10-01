# 6. Configuration

All runtime configuration flows through `vca_code/config.py`. There is exactly
one required secret.

---

## 6.1 Environment variables

| Variable | Required | Default | Read by |
|---|---|---|---|
| `GEMINI_API_KEY` | **yes** | — | `Config.gemini_api_key` |
| `GEMINI_MODEL` | no | `gemini-2.5-flash` | `Config.gemini_model` |
| `VERCEL` | set by platform | unset | `Config` → picks `runtime_root` |
| `LTP_REMOTE_SERVER` | set in code | `https://api.languagetool.org` | `language_tool_python` |

`GEMINI_API_KEY` is validated in `Config._validate()`, which raises
`EnvironmentError` naming every missing key. Because `api/router.py` constructs
`Config()` at import time, a missing key fails application startup rather than
the first request — intentional fail-fast behaviour, and worth knowing when a
deployment "won't boot" with no request in the logs.

`LTP_REMOTE_SERVER` is set by both entrypoints (`vca_code/main.py` and
`api/index.py`) **before** `language_tool_python` is imported, because the
library reads it at import time. Moving that assignment below the imports would
silently break grammar checking.

---

## 6.2 The `.env` file

Expected at `VCA/vca-without-azure/.env` — `Config` resolves it as
`Path(__file__).resolve().parent.parent / ".env"` from inside `vca_code/`.

```ini
# VCA/vca-without-azure/.env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

`.env` is listed in `.gitignore` and must stay out of version control.

A different path can be passed explicitly: `Config(env_path="/path/to/.env")`.

On Vercel there is no `.env` file — set the variables in the project's
Environment Variables settings instead. `load_dotenv` on a non-existent path is
a silent no-op, so the real environment is used unchanged.

---

## 6.3 Model selection

`gemini-2.5-flash` is the default: fast and inexpensive, which matters because
every request makes at least one Gemini call and the pipeline is latency-bound.
Any model the account can access and that accepts audio input works — set
`GEMINI_MODEL` to override. The readiness probe fails fast on an invalid or
inaccessible model name, so a typo surfaces as a clear startup error rather
than a confusing transcription failure.

---

## 6.4 Folder layout and `runtime_root`

```python
if os.environ.get("VERCEL"):
    self.runtime_root = Path("/tmp/vca")
else:
    self.runtime_root = self.project_root      # VCA/vca-without-azure/
```

| Folder | Path under `runtime_root` | Contents |
|---|---|---|
| Audio input | `audio_files/` | Uploads and FFmpeg output |
| Transcripts | `transcript/` | `<base>_transcript.txt` |
| JSON output | `json_output/` | Per-stage metrics and the score report |
| Logs | `log/` | `vca_run_<timestamp>.log` |

All four are created by `_ensure_folders_exist()` with
`mkdir(parents=True, exist_ok=True)` on every `Config()` construction.

**Why the branch exists:** Vercel deploys onto a read-only filesystem; only
`/tmp` is writable. Without it, `mkdir` raises on every cold start and nothing
serves. `VERCEL` is set automatically by the platform, so no manual
configuration is needed — but note the flip side: any *other* serverless host
with a read-only filesystem will fail unless you set `VERCEL=1` or extend the
condition.

### `/tmp` is ephemeral and shared

On serverless, `/tmp` lives for the lifetime of the container, not the request.
Two consequences:

- **Artifacts accumulate.** Transcripts and JSON files are written on every
  request and never cleaned up. A long-lived warm container slowly fills its
  `/tmp` allowance.
- **Only the upload is deleted.** The `finally` block in `api/router.py` unlinks
  the original upload. A WAV that FFmpeg *derived* from a non-WAV input has a
  different path and stays behind.

If this is deployed under real traffic, add cleanup of `transcript/` and
`json_output/` — or stop writing them in serverless mode and keep the artifacts
as a local-development aid only.

### Local runs write into the repository

Locally, `runtime_root` is the project folder, so running the API or the test
scripts creates `audio_files/`, `transcript/`, `json_output/` and `log/`
directly inside `VCA/vca-without-azure/`. `.gitignore` already excludes their
contents:

```
VCA/vca-without-azure/audio_files/*
VCA/vca-without-azure/log/*
VCA/vca-without-azure/transcript/*
VCA/vca-without-azure/json_output/*
```

---

## 6.5 FFmpeg resolution

FFmpeg is needed **only** for non-WAV uploads. Three mechanisms exist, and they
are worth distinguishing:

### 1. Bundled binary (what `vercel.json` ships)

`bin/ffmpeg` is a statically linked x86-64 Linux ELF executable, about 76 MB.
`vca_code/main.py` locates it, tries to add the execute bit, and prepends
`bin/` to `PATH`:

```python
BASE_DIR = Path(__file__).resolve().parent.parent
if not (BASE_DIR / "bin").exists():
    BASE_DIR = Path(os.getcwd())          # Vercel bundling fallback
FFMPEG_BIN = BASE_DIR / "bin" / "ffmpeg"
```

The `chmod` is wrapped in `try/except` because the deployment filesystem is
read-only; it prints a notice and continues rather than failing startup.

**Path mismatch to be aware of:** the binary lives at the **repository root**
(`./bin/ffmpeg`), while `BASE_DIR` resolves to `VCA/vca-without-azure/`. The
`bin` folder is not there, so the fallback to `os.getcwd()` is the only thing
that can find it, and only if the process happens to be started from the
repository root. Locally, `python main.py` from `vca_code/` finds neither path.
See [09-known-issues.md](09-known-issues.md).

### 2. `static_ffmpeg` (in `api/index.py` only)

```python
import static_ffmpeg
static_ffmpeg.add_paths()
```

A cleaner approach — the package downloads and registers platform-appropriate
binaries, removing 76 MB from the repository. But `api/index.py` is not wired
into `vercel.json`, and `static-ffmpeg` is **not** in `requirements.txt`, so
this path is currently non-functional.

### 3. System FFmpeg (local development)

`AudioFileHandler` only ever calls `shutil.which("ffmpeg")`, so any FFmpeg on
`PATH` works:

```bash
sudo apt install ffmpeg      # Debian / Ubuntu
brew install ffmpeg          # macOS
```

This is the simplest option for local work and the one to prefer.

### Behaviour when FFmpeg is absent

Nothing fails at startup. `AudioFileHandler.__init__` logs "FFmpeg not found.
WAV files will be processed directly." and only a non-WAV upload raises
`EnvironmentError` → HTTP `400` with a message telling the caller to send WAV.
Since the browser UI always sends WAV, a server without FFmpeg is fully
functional for the normal path.

---

## 6.6 Dependencies

`VCA/requirements.txt`:

```
fastapi>=0.110.0          # web framework
uvicorn>=0.28.0           # ASGI server (local)
pydantic>=2.6.0           # FastAPI's validation layer
python-multipart>=0.0.9   # required for UploadFile / multipart parsing
google-genai              # Gemini SDK
python-dotenv             # .env loading
requests                  # (not imported anywhere)
textblob                  # (not imported anywhere)
numpy                     # array maths in metrics and pitch analysis
scipy                     # (not imported directly; a librosa dependency)
pandas                    # (not imported anywhere)
ffmpeg-python             # (not imported; FFmpeg is called via subprocess)
librosa                   # audio loading, silence split, pyin, RMS
language-tool-python      # grammar checking (remote mode)
```

Only three of these are pinned, with floors rather than exact versions:
`fastapi`, `uvicorn`, `pydantic`. The rest float, which means a fresh install
can pick up a breaking major release. `librosa` in particular pulls a large
transitive tree (`numba`, `llvmlite`, `soundfile`, `audioread`, `scikit-learn`)
and is the main driver of install size and cold-start time.

**Four declared packages are unused:** `requests`, `textblob`, `pandas` and
`ffmpeg-python`. `scipy` is not imported directly either, though librosa needs
it. Removing the genuinely unused four would meaningfully shrink the deployment
bundle. Conversely, `static-ffmpeg` is **imported** by `api/index.py` but
**not declared**.

### Location problem

`requirements.txt` sits at `VCA/requirements.txt`, one level **above**
`VCA/vca-without-azure/`, where `vercel.json` lives. Vercel installs
dependencies from the configured Root Directory, so a Root Directory of
`VCA/vca-without-azure` will not see this file. See
[07-deployment.md](07-deployment.md).

---

## 6.7 Tunable constants

Not environment variables — these are class constants, changed in code.

| Constant | Location | Value | Effect |
|---|---|---|---|
| `TARGET_SAMPLE_RATE` | `AudioFileHandler` | 16000 | FFmpeg output rate |
| `TARGET_CHANNELS` | `AudioFileHandler` | 1 | FFmpeg output channels |
| `TOP_DB` | `MetricsCalculator` | 30 | Silence threshold in dB below peak |
| `PAUSE_THRESHOLD_SEC` | `MetricsCalculator` | 0.3 | Minimum gap counted as a pause |
| `LONG_PAUSE_THRESHOLD_SEC` | `MetricsCalculator` | 1.5 | Gap counted as a long pause |
| `FILLER_WORDS` | `MetricsCalculator` | 11 entries | What counts as a filler |
| `FMIN_NOTE` / `FMAX_NOTE` | `PitchAnalyzer` | `C2` / `C7` | PYIN search range (~65–2093 Hz) |
| `WEIGHTS` | `VCAScorer` | 5 weights summing to 1.0 | Dimension importance |
| `max_retries` / `retry_delays` | `api/router.py` | 3 / `[5, 10]` | Readiness retry policy |
| `total_steps` | `api/router.py` | 8 | Denominator in `[STEP n/8]` log lines |

`TOP_DB` is the one to scrutinise during calibration — it is a fixed absolute
threshold applied to recordings made in unknown acoustic conditions, and it
directly drives the fluency score. See
[04-scoring-methodology.md §4.9](04-scoring-methodology.md#49-how-to-tune-the-rubric).

---

## 6.8 Secrets handling

- `GEMINI_API_KEY` is the only secret. It reaches the process from `.env`
  locally or from platform environment variables in deployment.
- `.env`, `venv/`, `*.exe` and `__pycache__/` are all gitignored.
- The key is never logged. `GeminiReadinessChecker` logs only pass/fail.
- **Transcript text is sent to `api.languagetool.org`**, a third-party public
  service, for grammar checking. If recordings could contain anything
  confidential, this is the data-flow boundary to review first — the remedy is
  running a self-hosted LanguageTool server and pointing
  `LTP_REMOTE_SERVER` at it.
- **Audio is uploaded to Gemini's file store and never deleted.** Files
  accumulate against the account. Calling `client.files.delete()` after
  transcription would close both the storage leak and the retention exposure.
