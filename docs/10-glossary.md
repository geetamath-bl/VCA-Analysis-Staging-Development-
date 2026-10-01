# 10. Glossary

Terms used across this documentation and in the code, with the specific meaning
they carry in this project.

---

### Articulation rate

Words per minute counted against **speaking time only**, with pauses removed:

```
articulation_rate = total_words / (total_duration − total_pause_time) × 60
```

Always higher than WPM. Computed and stored in `*_metrics.json` but **not used
by the scorer** — pause behaviour is already scored by the fluency dimension, so
using both would penalise pausing twice.

---

### Coefficient of variation (CV)

Standard deviation expressed as a percentage of the mean:

```
CV = σ / μ × 100
```

Used for both pitch and volume variability. The reason it is preferred over raw
standard deviation is fairness across speakers: a deep voice varying by 20 Hz
around 100 Hz and a high voice varying by 40 Hz around 200 Hz both have a CV of
20 % and score identically. Raw Hz spread would systematically favour
higher-pitched speakers.

---

### F0 / Fundamental frequency

The lowest frequency of a periodic waveform — perceptually, the **pitch** of a
voice. Measured in Hz. Typical adult speaking ranges run roughly 85–180 Hz for
lower voices and 165–255 Hz for higher ones, which is why `PitchAnalyzer`
searches a generous C2–C7 window (≈65–2093 Hz) rather than a narrow one.

Unvoiced sounds (`s`, `f`, `t`, silence) have no F0, so `librosa.pyin` returns
`NaN` for those frames and the analyser filters them out before computing
statistics.

---

### Filler word

A word that fills conversational space without contributing meaning. This
project counts eleven entries (`MetricsCalculator.FILLER_WORDS`):

```
um   uh   umm   uhh   like   you know
actually   basically   literally   so
```

Two caveats documented in [09-known-issues.md](09-known-issues.md): `"you know"`
can never match because the tokeniser emits single words, and `like` / `so` are
counted even in legitimate uses.

Note that fillers only reach the counter because `TRANSCRIPTION_PROMPT`
explicitly asks Gemini to preserve them — most speech-to-text systems strip them
silently.

---

### FFmpeg

The standard open-source audio/video conversion tool. Used here to convert
non-WAV uploads to 16 kHz mono 16-bit PCM WAV, invoked via `subprocess`:

```
ffmpeg -y -i <input> -ar 16000 -ac 1 -sample_fmt s16 <output>
```

Optional — WAV uploads bypass it entirely, and the browser UI converts
client-side so the normal path never needs it.

---

### Gemini

Google's family of multimodal LLMs. Used here for **speech-to-text only**,
through the `google-genai` SDK. Default model `gemini-2.5-flash`, chosen for
latency and cost. Audio is uploaded via `client.files.upload` and transcribed
with `generate_content` under a prompt that requests strict JSON.

---

### LanguageTool

An open-source grammar and style checker. This project uses the **public remote
API** at `api.languagetool.org` rather than a local instance, because
`language_tool_python` would otherwise require a Java runtime, which serverless
Python environments do not provide.

Each flagged issue carries a `rule_id` and a `message`, both written to the run
log. A self-hosted server can be substituted via `LTP_REMOTE_SERVER`.

---

### Long pause

A pause exceeding `LONG_PAUSE_THRESHOLD_SEC = 1.5` seconds. Each one costs 10
points off the fluency base score, floored at 0.

---

### Pause

A gap longer than `PAUSE_THRESHOLD_SEC = 0.3` seconds between consecutive
non-silent audio intervals, as detected by `librosa.effects.split(y, top_db=30)`.

Detected **acoustically**, not from word timestamps — Gemini does not return
reliable word-level timing, so the Azure variant's timestamp-based approach was
replaced with silence detection.

Only *internal* gaps count: leading and trailing silence falls outside the
non-silent intervals by construction, so a recording that starts or ends with
dead air is not penalised for it.

---

### PYIN

Probabilistic YIN — the pitch-tracking algorithm used via `librosa.pyin`. An
extension of the YIN autocorrelation method that estimates a probability
distribution over candidate pitches per frame, making it more robust on noisy
recordings than plain YIN. Returns `NaN` for unvoiced frames.

---

### RMS energy

Root-mean-square amplitude per analysis frame, from
`librosa.feature.rms(y=y)[0]`. A proxy for perceived **loudness**. Its CV is the
volume-variability input to the expressiveness score.

More contaminated by recording conditions than F0 is — microphone distance and
input gain both move it — which is why it carries 40 % weight against pitch's
60 %.

---

### `runtime_root`

The base directory for all runtime-generated files, chosen by `Config`:

```python
runtime_root = Path("/tmp/vca") if os.environ.get("VERCEL") else project_root
```

The split exists because Vercel's deployment filesystem is read-only and only
`/tmp` is writable. Everything — `audio_files/`, `transcript/`, `json_output/`,
`log/` — hangs off it.

---

### Serverless / cold start

A deployment model where the platform runs the application on demand rather than
keeping a process alive. A **cold start** is a request that arrives with no warm
container: the platform must import the application first, which here means
loading librosa (slow) and running the Gemini readiness probe (one API call).

The consequences visible in this codebase: a read-only filesystem (hence
`runtime_root`), process-global caches that only help within a container's
lifetime (`CACHED_GEMINI_CLIENT`), and a bundle size limit that makes the 76 MB
FFmpeg binary and the unused `pandas` dependency expensive.

---

### Silence threshold (`top_db`)

`librosa.effects.split`'s sensitivity parameter: audio more than `top_db`
decibels below the clip's peak is treated as silence. Set to **30** here.

The single most consequential tuning parameter in the system, because it decides
what counts as a pause and therefore drives the fluency score (25 % of the
total). It is a **fixed absolute threshold applied to recordings made in unknown
acoustic conditions**: a noisy room raises the noise floor, fewer gaps clear the
threshold, and fluency scores rise spuriously. See
[04-scoring-methodology.md §4.9](04-scoring-methodology.md#49-how-to-tune-the-rubric).

---

### TTR — Type-Token Ratio

Lexical diversity: distinct words ("types") divided by total words ("tokens").

```
TTR = unique_words / total_words
```

Scored against a **two-sided** band (0.50–0.75 is best) because a very high TTR
usually signals a sample too short to be meaningful rather than impressive
vocabulary.

Its known weakness is length sensitivity — TTR falls mechanically as a
transcript grows, because function words repeat. The bands here implicitly
assume a recording of a few minutes.

---

### VCA — Verbal Communication Ability

The composite score this system produces, and the name of the project. A
weighted sum of five dimensions:

```
VCA = 0.20·pace + 0.25·fluency + 0.15·filler
    + 0.20·expressiveness + 0.20·vocab_grammar
```

Reported 0–100 with a rating label. The practical floor is **25**, not 0,
because most sub-scorers have non-zero minimums — see
[04-scoring-methodology.md §4.10](04-scoring-methodology.md#410-attainable-ranges).

---

### WAV / PCM / 16 kHz mono

The canonical audio format throughout the pipeline:

| Property | Value | Why |
|---|---|---|
| Container | RIFF/WAVE | Uncompressed, universally readable |
| Encoding | 16-bit signed PCM (`s16`) | Lossless, no decode step needed |
| Sample rate | 16 000 Hz | The speech-processing standard; captures everything up to 8 kHz, which covers intelligible speech |
| Channels | 1 (mono) | Speech needs no stereo; halves the payload |

The browser encodes to this format with `OfflineAudioContext` plus a hand-written
RIFF header (`bufferToWave`), and FFmpeg produces the same format server-side.

---

### WPM — Words per minute

Gross speaking rate, **including** pause time:

```
wpm = total_words / total_duration_sec × 60
```

The sole input to the pace score. Word count comes from the transcript; duration
comes from the waveform. Target window 120–160 WPM, the conventional range for
clear presentation speech.

Contrast with **articulation rate**, which excludes pauses.
