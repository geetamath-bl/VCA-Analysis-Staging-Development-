# VCA — Verbal Communication Ability Analyzer

VCA takes a short audio recording of someone speaking and returns a scored
assessment of how well they communicate verbally: how fast they speak, how
fluently, how often they reach for filler words, how expressive their voice
is, and how rich and correct their language is.

The whole system runs on **Google Gemini** for speech-to-text and on **local
signal processing** (librosa) plus **LanguageTool** for everything else. There
is no Azure dependency — this repository is the "without Azure" variant of the
pipeline.

```
  audio file ──► WAV ──► Gemini transcript ──┬──► pace / pause / filler metrics
                   │                         ├──► pitch & volume metrics
                   │                         └──► vocabulary & grammar metrics
                   │                                        │
                   └────────────────────────────────────────┴──► weighted VCA score
```

---

## At a glance

| | |
|---|---|
| **Backend** | Python 3, FastAPI, Uvicorn |
| **Speech-to-text** | Google Gemini (`gemini-2.5-flash` by default) |
| **Audio DSP** | librosa / NumPy (pitch, volume, pause detection) |
| **Grammar** | LanguageTool public API (`api.languagetool.org`) |
| **Frontend** | Vanilla HTML / CSS / JavaScript, Web Audio API |
| **Deployment target** | Vercel serverless (`@vercel/python`) |
| **Public endpoint** | `POST /vca/analyze` (multipart audio upload) |

---

## Repository layout

```
.
├── bin/
│   └── ffmpeg                       Statically linked FFmpeg binary (~76 MB)
├── VCA/
│   ├── requirements.txt             Python dependencies
│   └── vca-without-azure/
│       ├── vercel.json              Vercel build + routing config
│       ├── api/
│       │   ├── index.py             Alternate serverless entrypoint
│       │   └── router.py            /vca/analyze endpoint + orchestration
│       ├── vca_code/
│       │   ├── main.py              FastAPI app, FFmpeg bootstrap, static mount
│       │   ├── config.py            .env loading, folder layout, validation
│       │   ├── logger_setup.py      Dual console + file logger
│       │   ├── gemini_readiness.py  Pre-flight Gemini API check
│       │   ├── audio_utils.py       Format validation + WAV conversion
│       │   ├── transcription.py     Gemini upload + transcript parsing
│       │   ├── transcription_prompt.py  The transcription prompt
│       │   ├── metrics_calculator.py    Pace, pauses, fillers
│       │   ├── pitch_analyzer.py        F0 and RMS variability
│       │   ├── vocab_grammar_analyzer.py  TTR + grammar errors
│       │   ├── scorer.py            Rubric and weighted composite score
│       │   └── test_*.py            Manual smoke scripts (not pytest)
│       └── frontend/
│           ├── index.html           Upload / record UI
│           ├── style.css            Styling
│           └── script.js            Client-side WAV encoding + fetch
└── docs/                            ← full documentation (start here)
```

---

## Documentation

| Document | What it covers |
|---|---|
| [docs/01-architecture.md](docs/01-architecture.md) | System design, request lifecycle, data flow, sequence diagrams |
| [docs/02-module-reference.md](docs/02-module-reference.md) | Every class and method, file by file |
| [docs/03-api-reference.md](docs/03-api-reference.md) | HTTP endpoints, payloads, status codes, errors |
| [docs/04-scoring-methodology.md](docs/04-scoring-methodology.md) | The complete rubric, thresholds, weights, worked example |
| [docs/05-frontend.md](docs/05-frontend.md) | UI structure, recording, in-browser WAV encoding |
| [docs/06-configuration.md](docs/06-configuration.md) | Environment variables, folder layout, runtime paths |
| [docs/07-deployment.md](docs/07-deployment.md) | Local setup and Vercel deployment, including known pitfalls |
| [docs/08-testing.md](docs/08-testing.md) | The smoke scripts, how to run them, suggested test strategy |
| [docs/09-known-issues.md](docs/09-known-issues.md) | Verified bugs, gaps and risks found while documenting |
| [docs/10-glossary.md](docs/10-glossary.md) | Terms: WPM, TTR, CV, PYIN, articulation rate, etc. |

---

## Quickstart (local)

```bash
# 1. Install dependencies
python -m venv venv && source venv/bin/activate
pip install -r VCA/requirements.txt

# 2. Provide a Gemini API key
cat > VCA/vca-without-azure/.env <<'ENV'
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
ENV

# 3. Run the API
cd VCA/vca-without-azure/vca_code
python main.py          # serves on http://localhost:8000
```

Open `http://localhost:8000` for the UI, or `http://localhost:8000/docs` for
the auto-generated OpenAPI explorer.

> FFmpeg is only needed for **non-WAV** uploads. The browser UI already
> converts everything to 16 kHz mono WAV before upload, so a server without
> FFmpeg still works for the normal path. See
> [docs/06-configuration.md](docs/06-configuration.md#65-ffmpeg-resolution).

---

## The scores you get back

| Score | Weight | Driven by |
|---|---|---|
| Pace | 20 % | Words per minute |
| Fluency | 25 % | Pauses per minute, long-pause penalty |
| Filler | 15 % | Filler words as % of all words |
| Expressiveness | 20 % | Pitch CV (60 %) + volume CV (40 %) |
| Vocabulary & Grammar | 20 % | Type-Token Ratio (50 %) + errors per 100 words (50 %) |
| **Overall** | — | Weighted sum, 0–100, mapped to a rating label |

Ratings: `≥85 Excellent`, `≥70 Good`, `≥50 Fair`, otherwise
`Needs Improvement`. Full derivation in
[docs/04-scoring-methodology.md](docs/04-scoring-methodology.md).
