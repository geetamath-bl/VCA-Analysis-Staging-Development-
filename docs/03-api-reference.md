# 3. API reference

Base URL locally: `http://localhost:8000`.
Interactive OpenAPI explorer: `GET /docs`. Raw schema: `GET /openapi.json`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Serves the frontend (or a JSON status object if absent) |
| `GET` | `/health` | Liveness probe |
| `GET` | `/static/*` | Frontend assets (`style.css`, `script.js`) |
| `POST` | `/vca/analyze` | Analyse an audio file and return scores |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | FastAPI-generated documentation |

No endpoint requires authentication.

---

## 3.1 `GET /`

Returns `frontend/index.html` as a `FileResponse`.

If the frontend folder is missing from the deployment bundle, returns `200`
with:

```json
{ "status": "success", "message": "VCA API is running", "docs": "/docs" }
```

That fallback makes it easy to tell "the API is fine, the static assets did not
ship" apart from "the API is down".

---

## 3.2 `GET /health`

```json
{ "status": "healthy", "service": "VCA API" }
```

Always `200`. A pure liveness probe: it does **not** check Gemini reachability,
LanguageTool reachability, or FFmpeg availability. A healthy response therefore
does not imply `/vca/analyze` will succeed. Use it for uptime monitoring and
load-balancer checks only.

---

## 3.3 `POST /vca/analyze`

The one endpoint that does work.

### Request

```
POST /vca/analyze
Content-Type: multipart/form-data
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | file part | yes | The audio recording |

### Accepted formats

| Case | Requirement |
|---|---|
| `.wav` | Always accepted — no FFmpeg needed |
| Anything else (`.mp3`, `.m4a`, `.ogg`, `.mp4`, …) | Requires FFmpeg on the server; converted to 16 kHz mono 16-bit PCM |

The browser UI always converts client-side to 16 kHz mono WAV before uploading,
so the normal path never touches server-side FFmpeg. The UI advertises
MP4, MP3, WAV, OGG and M4A.

**WAV uploads are passed through untouched.** A 44.1 kHz stereo WAV sent by
`curl` is analysed at its native rate rather than resampled. The analysis still
works, but numbers are not strictly comparable across sample rates.

### Practical size limit

The browser re-encodes any WAV over **3 MB** to shrink it before upload. That
threshold exists because serverless platforms cap request body size (Vercel's
limit is a few MB), not because of anything in the Python code. For direct API
clients, keep uploads comfortably under a few megabytes — at 16 kHz mono
16-bit that is roughly 90 seconds per megabyte, so a 3 MB budget allows about
four to five minutes of speech.

### Success — `200 OK`

```json
{
  "status": "success",
  "filename": "interview_converted.wav",
  "report": {
    "pace_score": 100.0,
    "fluency_score": 80.0,
    "filler_score": 100.0,
    "expressiveness_score": 94.0,
    "vocab_grammar_score": 90.0,
    "overall_score": 92.3,
    "rating": "Excellent"
  }
}
```

| Field | Type | Range | Meaning |
|---|---|---|---|
| `status` | string | `"success"` | Always this value on `200` |
| `filename` | string | — | The **client-supplied** name, echoed back verbatim |
| `report.pace_score` | number | 40–100 | Speaking rate |
| `report.fluency_score` | number | 0–100 | Pause behaviour |
| `report.filler_score` | number | 20–100 | Filler word discipline |
| `report.expressiveness_score` | number | 30–100 | Pitch and volume variation |
| `report.vocab_grammar_score` | number | 40–100 | Lexical range and correctness |
| `report.overall_score` | number | 0–100 | Weighted composite |
| `report.rating` | string | — | `Excellent` / `Good` / `Fair` / `Needs Improvement` |

The sub-score ranges are narrower than 0–100 because most scorers use discrete
bands with a non-zero floor. Only `fluency_score` can reach 0, via the
long-pause penalty. See
[04-scoring-methodology.md](04-scoring-methodology.md#410-attainable-ranges).

The richer per-stage metrics (WPM, pause counts, TTR, mean pitch, grammar rule
IDs…) are written to `json_output/` on the server but **not** returned. If a
client needs them, the response model in `api/router.py` has to be widened.

### Errors

Every error body is FastAPI's standard shape:

```json
{ "detail": "<message>" }
```

| Status | Condition | Example `detail` |
|---|---|---|
| `400` | Audio could not be prepared | `Audio Preparation Error: FFmpeg is not available on this server. Please upload a WAV file. Received: .m4a` |
| `422` | `file` part missing or malformed | FastAPI validation error body |
| `429` | Gemini quota exhausted during the readiness probe | `Gemini API rate limit reached. Please wait a minute before analyzing another file.` |
| `429` | Gemini quota exhausted during transcription | `Gemini API rate limit exceeded during analysis. Please wait ~30 seconds and retry.` |
| `500` | Readiness probe failed for a non-quota reason | `Gemini Readiness Failed: <reason>` |
| `500` | Gemini API error during the pipeline | `Gemini API Error: <reason>` |
| `500` | Any other pipeline failure | `<str(exception)>` |

Two distinct `429` messages exist on purpose — they tell you *where* the quota
ran out, which matters because the readiness probe is cached and the
transcription call is not.

### Error semantics worth relying on

- **Uploaded files are always cleaned up.** Each error path unlinks the input
  before raising, and a `finally` block unlinks it again defensively.
- **The readiness probe is retried, transcription is not.** `get_gemini_client()`
  retries up to three times with 5 s then 10 s backoff. A `429` during
  transcription surfaces immediately. Clients should implement their own
  backoff.
- **Grammar failure is silent.** If LanguageTool is unreachable, the request
  still returns `200` with zero grammar errors, which *raises* the
  vocab/grammar sub-score. There is no field in the response indicating this
  happened — only the server log says so.
- **A blank transcript still returns `200`.** Silent or unintelligible audio
  produces empty metric dicts, and the scorer's `.get(key, 0)` defaults turn
  those into a real-looking score. Treat an `overall_score` around 60–70 with a
  very short recording as suspect.

### Examples

```bash
# WAV upload
curl -X POST http://localhost:8000/vca/analyze \
  -F "file=@interview.wav"

# Non-WAV (needs server-side FFmpeg)
curl -X POST http://localhost:8000/vca/analyze \
  -F "file=@interview.m4a"
```

```javascript
const formData = new FormData();
formData.append("file", wavFile);

const res = await fetch("/vca/analyze", { method: "POST", body: formData });
if (!res.ok) throw new Error(`Server returned status: ${res.status}`);
const { report } = await res.json();
```

```python
import requests

with open("interview.wav", "rb") as f:
    r = requests.post(
        "http://localhost:8000/vca/analyze",
        files={"file": ("interview.wav", f, "audio/wav")},
        timeout=300,
    )
r.raise_for_status()
print(r.json()["report"])
```

### Latency

The request is dominated by two network round trips and one CPU-bound stage:

| Stage | Typical cost |
|---|---|
| Upload + optional FFmpeg conversion | < 1 s for a few MB |
| Gemini readiness probe | ~1 s, **once per process** |
| Gemini file upload + transcription | several seconds, scales with audio length |
| `librosa.pyin` pitch analysis | the slowest local stage; seconds to tens of seconds, scales with duration × sample rate |
| LanguageTool remote check | ~1 s |
| Scoring | negligible |

Budget tens of seconds for a multi-minute recording, and set generous client
timeouts. On serverless, confirm the platform's function timeout exceeds the
worst case for your longest expected audio.

---

## 3.4 CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
```

Fully open, which suits a public demo served from the same origin. Two things to
note:

1. `allow_origins=["*"]` combined with `allow_credentials=True` is rejected by
   browsers — the spec forbids a wildcard origin on credentialed requests, so
   cookie-bearing cross-origin calls will fail regardless of this setting.
2. Combined with the absence of authentication, any website can drive this
   endpoint and spend your Gemini quota. Before anything resembling production,
   pin `allow_origins` to known hosts and add an API key or session check.
