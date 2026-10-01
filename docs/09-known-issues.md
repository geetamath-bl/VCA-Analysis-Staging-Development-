# 9. Known issues and risks

Everything here was found by reading the code while writing this
documentation. Each entry names the file, explains the consequence, and proposes
a fix. **No code was changed** — this is a findings register, not a changelog.

Severity: 🔴 breaks or corrupts behaviour · 🟠 security or correctness risk ·
🟡 maintenance or polish.

---

## 9.1 🔴 Silent or unintelligible audio returns a plausible "Good" score

**Files:** `vca_code/scorer.py`, `metrics_calculator.py`,
`vocab_grammar_analyzer.py`

When nothing is recognised, `MetricsCalculator.compute_metrics` and
`VocabGrammarAnalyzer.analyze` both return `{}`. `VCAScorer.compute_score` reads
every field through `.get(key, 0)`, so the empty dicts become zeros — and zero
is *favourable* in three of the five dimensions.

Verified arithmetic for a fully silent recording:

| Dimension | Input | Score | Why |
|---|---|---|---|
| Pace | `wpm = 0` | 40 | Falls into the `else` band |
| Fluency | `num_pauses=0`, `duration=0` | **100** | `duration=0` → `minutes=1` → `0 pauses/min` → base 100, no long-pause penalty |
| Filler | `filler_ratio = 0` | **100** | 0 % is below the 2 % threshold |
| Expressiveness | both CVs 0 | 49.0 | Floors apply: `55×0.6 + 40×0.4` |
| Vocab & Grammar | `ttr=0`, `errors=0` | **80** | TTR 0 → 60, but 0 errors → a perfect 100 |

```
0.20×40 + 0.25×100 + 0.15×100 + 0.20×49 + 0.20×80 = 73.8  →  "Good"
```

**Silence scores 73.8 out of 100 and is labelled "Good".** The root cause is
that "no data" and "perfect data" are the same value in this scoring model.

**Fix:** reject the request before scoring.

```python
# in api/router.py, after transcription
if not transcript_text.strip():
    raise HTTPException(
        status_code=422,
        detail="No speech detected in the audio. Please upload a clearer recording.",
    )
```

Also guard `_score_fluency` against `total_duration_sec == 0` rather than
substituting `minutes = 1`, and have `compute_score` reject empty metric dicts
explicitly instead of defaulting them to zero.

---

## 9.2 🔴 `bin/ffmpeg` is outside every path that looks for it

**Files:** `bin/ffmpeg`, `vca_code/main.py`, `vercel.json`

The binary is at the **repository root**. But:

- `main.py` computes `BASE_DIR = Path(__file__).resolve().parent.parent` →
  `VCA/vca-without-azure/`, which has no `bin` folder. The
  `if not (BASE_DIR / "bin").exists(): BASE_DIR = Path(os.getcwd())` fallback
  only helps if the process was started from the repository root.
- `vercel.json`'s `includeFiles: ["bin/ffmpeg"]` resolves relative to the Root
  Directory (`VCA/vca-without-azure/`) and matches nothing.

Net effect: FFmpeg is unavailable both locally (when run the documented way,
from `vca_code/`) and on Vercel. Non-WAV uploads return `400`. This is easy to
miss because the browser UI converts client-side and therefore still works end
to end.

**Fix (pick one):**

1. Move the binary to `VCA/vca-without-azure/bin/ffmpeg` — both paths then
   resolve. Costs 76 MB in the bundle.
2. Add `static-ffmpeg` to `requirements.txt`, call `static_ffmpeg.add_paths()`
   in `main.py` (as `api/index.py` already does), delete the binary. Smaller
   repository and bundle. **Recommended.**
3. Accept WAV-only operation, drop `bin/ffmpeg` from `includeFiles`, and
   document the `400` as intended behaviour.

---

## 9.3 🔴 `requirements.txt` is outside the Vercel Root Directory

**Files:** `VCA/requirements.txt`, `VCA/vca-without-azure/vercel.json`

`vercel.json` lives in `VCA/vca-without-azure/`, so the project's Root Directory
must be set there — but `requirements.txt` is one level up at `VCA/`. Vercel
installs dependencies from the Root Directory and will not find it, producing a
deployment with no FastAPI, librosa or Gemini SDK.

**Fix:** move `requirements.txt` into `VCA/vca-without-azure/`.

---

## 9.4 🔴 `api/index.py` imports an undeclared package

**Files:** `api/index.py`, `VCA/requirements.txt`

```python
import static_ffmpeg
static_ffmpeg.add_paths()
```

`static-ffmpeg` is not in `requirements.txt`, so this module raises
`ModuleNotFoundError` on import. It is latent today because `vercel.json` points
at `vca_code/main.py` instead — but Vercel's filesystem-based Python routing
treats `api/*.py` as an automatic entrypoint, so anyone adopting that style
breaks immediately.

**Fix:** add `static-ffmpeg` to `requirements.txt` (and ideally adopt it in
`main.py` too, resolving 9.2 at the same time), or delete `api/index.py`.

---

## 9.5 🟠 No authentication on an endpoint that spends money

**Files:** `api/router.py`, `vca_code/main.py`

`POST /vca/analyze` is unauthenticated, has no rate limiting, and CORS is fully
open. Every call consumes Gemini quota. A trivial script can exhaust the
project's quota or run up its bill, and any third-party website can drive the
endpoint from a visitor's browser.

**Fix:** require an API key or session token, add per-IP rate limiting, and
restrict CORS as in 9.7.

```python
from fastapi import Header, HTTPException

async def require_api_key(x_api_key: str = Header(...)):
    if x_api_key != config.api_key:
        raise HTTPException(401, "Invalid API key")

@router.post("/analyze", dependencies=[Depends(require_api_key)])
async def analyze_audio(...): ...
```

---

## 9.6 🟠 Client-controlled filename is used to build a filesystem path

**File:** `api/router.py`

```python
uploaded_path = config.audio_input_folder / file.filename
with open(uploaded_path, "wb") as buffer:
    shutil.copyfileobj(file.file, buffer)
```

`file.filename` comes from the client. A multipart part named
`../../something` makes `Path.__truediv__` resolve outside
`audio_input_folder`, so a crafted request can write anywhere the process has
permission to write. Overwriting application source is the obvious escalation.

Secondary problem: two concurrent requests uploading the same filename collide,
and the first request's `finally` block deletes the file the second is still
using.

**Fix:** never trust the supplied name. Generate your own and keep only the
extension.

```python
import uuid
safe_suffix = Path(file.filename or "").suffix.lower()
if safe_suffix not in {".wav", ".mp3", ".m4a", ".ogg", ".mp4", ".webm", ".flac"}:
    raise HTTPException(400, f"Unsupported file type: {safe_suffix or 'unknown'}")
uploaded_path = config.audio_input_folder / f"{uuid.uuid4().hex}{safe_suffix}"
```

This fixes the traversal and the collision together. Note `file.filename` is
still safely *echoed* in the response — the frontend uses `textContent`, so
there is no XSS path.

---

## 9.7 🟠 Wildcard CORS combined with credentials

**File:** `vca_code/main.py`

```python
allow_origins=["*"], allow_credentials=True
```

The Fetch standard forbids a wildcard `Access-Control-Allow-Origin` on
credentialed requests, so browsers reject this combination — credentialed
cross-origin calls fail regardless of intent. The setting is simultaneously too
permissive (any origin may call the unauthenticated endpoint) and non-functional
for its apparent purpose.

**Fix:** list real origins, or set `allow_credentials=False` if credentials are
not needed.

```python
allow_origins=["https://your-app.vercel.app", "http://localhost:8000"],
allow_credentials=True,
allow_methods=["GET", "POST"],
```

---

## 9.8 🟠 A LanguageTool outage silently raises the score

**File:** `vca_code/vocab_grammar_analyzer.py`

Both the constructor and `_check_grammar` swallow failures and return
`(0, [])` — zero grammar errors. The scorer rewards zero errors with a perfect
100 for the grammar half of the dimension. An outage therefore produces a
*higher* score, and the response contains no indication that grammar checking
did not run. Only the server log says so.

**Fix:** propagate the condition into the response so callers can distinguish
"no errors" from "not checked".

```python
metrics["grammar_checked"] = self.tool is not None and check_succeeded
```

Then either omit the grammar half from the composite and renormalise the
weights, or return `503` if grammar checking is considered essential.

---

## 9.9 🟠 Transcript text and audio leave the deployment permanently

**Files:** `vocab_grammar_analyzer.py`, `transcription.py`

Two outbound data flows deserve explicit sign-off:

1. **Full transcript text → `api.languagetool.org`**, a third-party public
   service, on every request.
2. **The audio file → Gemini's file store**, via `client.files.upload`, and it
   is **never deleted**. Files accumulate against the account indefinitely.

For interview or assessment recordings this is a data-retention question, not
just a housekeeping one.

**Fix:** delete the uploaded file after transcription, and self-host
LanguageTool if transcripts are sensitive.

```python
# transcription.py, after generate_content
finally:
    try:
        self.client.files.delete(name=uploaded_file.name)
    except Exception:
        self.logger.warning("Could not delete uploaded Gemini file.")
```

```bash
docker run -d -p 8010:8010 erikvl87/languagetool
# then: LTP_REMOTE_SERVER=http://localhost:8010
```

---

## 9.10 🟠 Derived files and artifacts are never cleaned up

**File:** `api/router.py`

The `finally` block unlinks `uploaded_path` — the *original* upload. When FFmpeg
converted a non-WAV input, the derived `.wav` has a different path and remains.
Transcripts and the five JSON artifacts are never removed either.

On serverless, `/tmp` is a fixed per-container allowance, so a warm container
under sustained traffic will eventually fail on writes.

**Fix:** clean up every produced path, not just the input.

```python
finally:
    for p in {uploaded_path, locals().get("wav_path")}:
        if p and Path(p).exists():
            try: Path(p).unlink()
            except Exception: pass
```

Consider making the JSON artifacts conditional on a `VCA_WRITE_ARTIFACTS` flag
so they stay a local-development aid rather than production output.

---

## 9.11 🟡 `"you know"` can never match

**File:** `vca_code/metrics_calculator.py`

`FILLER_WORDS` contains the two-word entry `"you know"`, but the tokeniser emits
single words:

```python
words = re.findall(r"\b[a-zA-Z']+\b", transcript_text.lower())
```

The entry is unreachable, so one of the most common English fillers is invisible
to the filler score.

**Fix:** match multi-word fillers against the raw text before tokenising.

```python
MULTIWORD_FILLERS = {"you know", "i mean", "sort of", "kind of"}
multi = sum(transcript_text.lower().count(ph) for ph in MULTIWORD_FILLERS)
filler_count = self._count_filler_words(words) + multi
```

---

## 9.12 🟡 `like` and `so` are counted as fillers unconditionally

**File:** `vca_code/metrics_calculator.py`

"I would **like** to explain" and "**So** the array stores…" are legitimate
uses, counted as fillers. On technical speech — which is exactly what the
existing fixture name (`array_vs_linkedlist_1`) suggests this system analyses —
this systematically inflates the filler ratio and depresses the score.

**Fix:** drop both from the set, or gate them on part-of-speech. A pragmatic
middle ground is to count `so` only sentence-initially and `like` only when not
followed by `to`/a noun phrase.

---

## 9.13 🟡 The long-pause penalty is not rate-normalised

**File:** `vca_code/scorer.py`

```python
return max(0, base - long_pauses * 10)
```

The base score is pauses *per minute*, but the penalty is an absolute count. Six
long pauses zero out a perfect base regardless of whether the recording is one
minute or ten, which makes fluency progressively harsher as duration grows —
the opposite of the intent.

**Fix:** normalise it.

```python
long_pause_penalty = (long_pauses / minutes) * 10
```

---

## 9.14 🟡 TTR bands assume a short recording

**Files:** `vocab_grammar_analyzer.py`, `scorer.py`

Type-Token Ratio falls mechanically as transcript length grows, because function
words repeat. The 0.50–0.75 target band implies a sample of a few minutes at
most. On a twenty-minute recording, an articulate speaker lands below 0.4 and is
scored 60 for lexical diversity.

**Fix:** use a length-robust measure — MTLD, or a moving-average TTR over
fixed-size windows — or make the bands a function of word count.

---

## 9.15 🟡 Incoming WAV files are not normalised

**File:** `vca_code/audio_utils.py`

`prepare_audio_file` returns a `.wav` path unchanged, so a 44.1 kHz stereo WAV is
analysed at its native rate. librosa loads with `sr=None`, so results are valid
but **not comparable** to 16 kHz mono runs: silence detection, PYIN and RMS all
behave differently at different rates and channel counts.

The browser UI hides this by always converting client-side. Any other client
(curl, Postman, a mobile app) does not.

**Fix:** always normalise server-side when FFmpeg is available, or resample in
librosa with `sr=16000, mono=True` at load time in both DSP stages.

---

## 9.16 🟡 The global logger's step counter is cumulative

**Files:** `api/router.py`, `logger_setup.py`

`logger` is a module-level `PipelineLogger` with `total_steps=8`. `current_step`
never resets, so the second request in a warm process logs `[STEP 9/8]`,
`[STEP 10/8]` and onwards. Cosmetic, but it makes logs hard to read and defeats
the purpose of numbered steps.

Related: `PipelineLogger.__init__` calls `handlers.clear()` on the shared
`"VCA_Pipeline"` logger, so constructing a second instance detaches the first
one's file handler. Any code creating two loggers loses output from one.

**Fix:** construct a per-request logger, or add a `reset_steps()` call at the top
of `analyze_audio`. Also consider a per-request correlation ID so concurrent
requests can be told apart in one log file.

---

## 9.17 🟡 Four declared dependencies are unused

**File:** `VCA/requirements.txt`

`requests`, `textblob`, `pandas` and `ffmpeg-python` are never imported
anywhere in the project. `pandas` in particular is large, and bundle size is a
real constraint on serverless (see [07-deployment.md](07-deployment.md)).

`scipy` is also not imported directly, but librosa requires it, so it should
stay — ideally with a comment saying why.

**Fix:** remove the four, keep `scipy` with a note, and pin versions. Only
`fastapi`, `uvicorn` and `pydantic` currently have constraints, and those are
floors rather than ranges — a fresh install can pick up a breaking major
release of `librosa` or `google-genai`.

---

## 9.18 🟡 No response caching for repeated uploads

**File:** `api/router.py`

Uploading the same audio twice re-runs the whole pipeline, including the Gemini
transcription call. For a tool where users iterate on the same recording, this
wastes the most expensive part of the request.

**Fix:** hash the audio content and cache the score report keyed by that hash.

---

## 9.19 🟡 Frontend discards the server's error message

**File:** `frontend/script.js`

```javascript
if (!response.ok) throw new Error(`Server returned status: ${response.status}`);
```

The `detail` string — the part that explains what to do, such as "wait a minute
before analyzing another file" — is never read. Users see a bare status number.
Separately, a `200` with a non-success body produces "Analysis failed. Please
check logs.", which end users cannot act on.

**Fix:**

```javascript
if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Server returned status: ${response.status}`);
}
```

---

## 9.20 🟡 The drop zone does not accept drops

**Files:** `frontend/index.html`, `script.js`

`#dropZone` carries drop-zone styling and the affordance of one, but no
`dragover` or `drop` listeners are registered. Dragging a file onto it does
nothing — only the "Browse File" label works.

**Fix:** register the two handlers and reuse the existing selection logic.

```javascript
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragging'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragging'));
dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragging');
    if (e.dataTransfer.files.length) {
        audioFileInput.files = e.dataTransfer.files;
        audioFileInput.dispatchEvent(new Event('change'));
    }
});
```

---

## 9.21 🟡 `report.rating || "Excellent"` defaults to the best label

**File:** `frontend/script.js`

A missing or empty `rating` displays **"Excellent"** regardless of the numeric
score. The fallback should be neutral.

**Fix:** `report.rating || "—"`.

---

## 9.22 🟡 Button label is reset to the upload tab's text

**File:** `frontend/script.js`

`processAndSendFile`'s `finally` block sets
`buttonElement.textContent = "⚡ Analyze Audio"` for whichever button was used,
so the record tab's `⚡ Analyze Recorded Audio` is overwritten after the first
analysis.

**Fix:** capture the original label before disabling and restore that.

```javascript
const originalLabel = buttonElement.textContent;
// ...
finally { buttonElement.disabled = false; buttonElement.textContent = originalLabel; }
```

---

## 9.23 🟡 The `test_*.py` scripts are not tests

**Files:** `vca_code/test_*.py`

Nine files match pytest's default discovery glob but contain no assertions and
execute at import. Running `pytest` would fire all nine during collection,
making real Gemini and LanguageTool calls. They also depend on a fixture
(`array_vs_linkedlist_1.m4a`) that is gitignored and absent, so the chain cannot
run on a clean clone.

One concrete bug in the chain: `test_pitch_analyzer.py` passes
`"array_vs_linkedlist_1_pitch_metrics"` as the base name, and `save_metrics`
appends `_pitch_metrics` itself, producing
`..._pitch_metrics_pitch_metrics.json`. `test_scorer.py` then cannot find its
input.

**Fix:** rename them out of the `test_*` namespace (`scripts/smoke/check_*.py`)
and add a real pytest suite. Full plan in [08-testing.md](08-testing.md).

---

## 9.24 🟡 Documentation and comment inaccuracies

| File | Issue |
|---|---|
| `vca-without-azure/README.md` | Says "Coming soon" for a fully implemented system |
| `scorer.py` | Class docstring says "the four metric dimensions" then lists five |
| `main.py` | Comment says "so pydub / ffmpeg-python find it"; neither is used — FFmpeg is invoked via `subprocess` |
| `pitch_analyzer.py` | File ends with trailing whitespace and no newline |
| `requirements.txt` | No trailing newline on the last line |
| `gemini_readiness.py` | Third import fallback references `app.services.*`, a layout that no longer exists |

---

## 9.25 Priority order

If this were a work queue, this is the order that maximises risk reduction per
unit of effort:

| Priority | Items | Rationale |
|---|---|---|
| **1 — Deploy blockers** | 9.3, 9.2, 9.4 | The deployment is incorrect or incomplete without these |
| **2 — Security** | 9.6, 9.5, 9.7 | Path traversal first; it is a write primitive |
| **3 — Correctness** | 9.1, 9.8, 9.10 | Scores that are silently wrong are worse than errors |
| **4 — Measurement quality** | 9.11, 9.12, 9.13, 9.14, 9.15 | Affects whether the scores mean anything |
| **5 — Test foundation** | 9.23, plus Tier 1 from [08-testing.md](08-testing.md) | Makes every later change safe |
| **6 — Polish** | 9.16–9.22, 9.24 | Low risk, improves the experience |

A reasonable first commit would be 9.3 + 9.2 + 9.6 + 9.1: the deployment
actually works, the write primitive is closed, and silence stops scoring
"Good" — four small, independent changes.
