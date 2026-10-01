# VCA without Azure

The Gemini-based variant of the Verbal Communication Ability pipeline. It
replaces the Azure Speech and Azure Blob dependencies of the original with:

| Concern | This variant uses |
|---|---|
| Speech-to-text | Google Gemini (`gemini-2.5-flash` by default) |
| Pace, pauses, fillers | librosa silence detection + transcript word counts |
| Pitch and volume | librosa PYIN and RMS — local signal processing |
| Grammar | LanguageTool public API (no Java runtime needed) |
| Storage | The local filesystem (`/tmp` on serverless) |

There is no Azure dependency anywhere in this folder.

## Contents

```
vca-without-azure/
├── vercel.json        Vercel build + routing config
├── api/
│   ├── index.py       Alternate serverless entrypoint (not wired up)
│   └── router.py      POST /vca/analyze — pipeline orchestration
├── vca_code/
│   ├── main.py        FastAPI app, FFmpeg bootstrap, static mount
│   ├── config.py      .env loading, folder layout, validation
│   ├── logger_setup.py
│   ├── gemini_readiness.py
│   ├── audio_utils.py
│   ├── transcription.py + transcription_prompt.py
│   ├── metrics_calculator.py
│   ├── pitch_analyzer.py
│   ├── vocab_grammar_analyzer.py
│   ├── scorer.py
│   └── test_*.py      Manual smoke scripts (not pytest)
└── frontend/          Vanilla HTML/CSS/JS upload + record UI
```

## Run it

```bash
pip install -r ../requirements.txt

cat > .env <<'ENV'
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
ENV

cd vca_code && python main.py        # http://localhost:8000
```

## Full documentation

The complete documentation set lives in [`../../docs/`](../../docs/):

- [Architecture](../../docs/01-architecture.md) — design, request lifecycle, trade-offs
- [Module reference](../../docs/02-module-reference.md) — every class and method
- [API reference](../../docs/03-api-reference.md) — endpoints, payloads, errors
- [Scoring methodology](../../docs/04-scoring-methodology.md) — the complete rubric
- [Frontend](../../docs/05-frontend.md) — UI, recording, in-browser WAV encoding
- [Configuration](../../docs/06-configuration.md) — env vars, folders, FFmpeg
- [Deployment](../../docs/07-deployment.md) — local, Vercel, container
- [Testing](../../docs/08-testing.md) — smoke scripts and a suggested test plan
- [Known issues](../../docs/09-known-issues.md) — verified bugs and risks
- [Glossary](../../docs/10-glossary.md) — WPM, TTR, CV, PYIN, and the rest

Before deploying, read
[the deployment pitfalls](../../docs/07-deployment.md#73-known-deployment-pitfalls) —
`requirements.txt` and `bin/ffmpeg` both currently sit outside the folder Vercel
builds from.
