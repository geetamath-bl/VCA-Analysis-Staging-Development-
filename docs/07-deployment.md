# 7. Deployment

---

## 7.1 Local development

### Prerequisites

- Python 3.10 or newer — `transcription.py` and `vocab_grammar_analyzer.py` use
  `tuple[str, list]` / `tuple[int, list]` builtin generics in annotations, and
  `api/router.py` uses `Path | None`.
- A Gemini API key.
- FFmpeg on `PATH`, optional — only for non-WAV uploads.

### Setup

```bash
git clone https://github.com/geetamath-bl/VCA-Analysis-Staging-Development-
cd VCA-Analysis-Staging-Development-

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r VCA/requirements.txt

cat > VCA/vca-without-azure/.env <<'ENV'
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
ENV
```

The librosa install pulls `numba`, `llvmlite`, `soundfile`, `audioread` and
`scikit-learn`, so expect it to take a few minutes.

### Run

```bash
cd VCA/vca-without-azure/vca_code
python main.py
```

Uvicorn starts on `0.0.0.0:8000` with `reload=True`.

| URL | What |
|---|---|
| `http://localhost:8000/` | The UI |
| `http://localhost:8000/docs` | OpenAPI explorer |
| `http://localhost:8000/health` | Liveness check |

### Running from the project root instead

`main.py` resolves its own paths, so this also works and has the advantage of
letting the `os.getcwd()` fallback find `bin/ffmpeg`:

```bash
cd VCA/vca-without-azure
uvicorn vca_code.main:app --reload --port 8000
```

### First-run checklist

```bash
# Is the key loading?
cd VCA/vca-without-azure/vca_code && python test_config.py

# Is Gemini reachable with that key and model?
python test_readiness.py
```

Both print directly to the console. See [08-testing.md](08-testing.md).

---

## 7.2 Vercel deployment

### What `vercel.json` declares

```json
{
  "version": 2,
  "builds": [
    {
      "src": "vca_code/main.py",
      "use": "@vercel/python",
      "config": { "includeFiles": ["bin/ffmpeg", "frontend/**"] }
    }
  ],
  "routes": [ { "src": "/(.*)", "dest": "vca_code/main.py" } ]
}
```

- `vca_code/main.py` is both the build source and the destination for **every**
  route. FastAPI handles all internal routing, so `/`, `/health`, `/static/*`,
  `/vca/analyze` and `/docs` all arrive at the same function.
- `includeFiles` pulls the FFmpeg binary and the frontend assets into the
  bundle; without it, `@vercel/python` ships only Python sources and the UI
  would 404 while non-WAV uploads would fail.

Because `vercel.json` lives in `VCA/vca-without-azure/`, the Vercel project's
**Root Directory must be set to `VCA/vca-without-azure`** — otherwise the config
is never read and paths do not resolve.

### Steps

1. **Import the repository** into Vercel.
2. **Set Root Directory** to `VCA/vca-without-azure`.
3. **Add environment variables** — `GEMINI_API_KEY`, and `GEMINI_MODEL` if you
   want to override the default. `VERCEL` is injected by the platform.
4. **Deploy.**

### Verify

```bash
curl https://<your-deployment>.vercel.app/health
# {"status":"healthy","service":"VCA API"}

curl -X POST https://<your-deployment>.vercel.app/vca/analyze \
  -F "file=@sample.wav"
```

Remember that `/health` passing says nothing about Gemini — the first
`/vca/analyze` call is the real smoke test.

---

## 7.3 Known deployment pitfalls

These are consequences of the current repository layout, verified by reading the
paths. They are the things most likely to bite on a fresh deploy.

### `requirements.txt` sits outside the Root Directory

`requirements.txt` is at `VCA/requirements.txt`, while the Root Directory must
be `VCA/vca-without-azure/`. Vercel installs from the Root Directory, so it will
not find this file and the build ships without FastAPI, librosa or the Gemini
SDK.

**Fixes, in order of preference:**

1. Move or copy `requirements.txt` into `VCA/vca-without-azure/`.
2. Keep one canonical copy at `VCA/` and symlink it.
3. Set Root Directory to `VCA/` and rewrite every path in `vercel.json` with a
   `vca-without-azure/` prefix.

Option 1 is the least surprising.

### `bin/ffmpeg` also sits outside the Root Directory

The binary is at the **repository root** (`./bin/ffmpeg`), so
`includeFiles: ["bin/ffmpeg"]` — resolved relative to `VCA/vca-without-azure/` —
matches nothing. And `main.py` computes `BASE_DIR` as `VCA/vca-without-azure/`,
where no `bin` folder exists, so it falls back to `os.getcwd()`, which on Vercel
is not the repository root either.

Net effect: **FFmpeg is unavailable in the deployment.** Non-WAV uploads return
`400`. The browser UI still works end to end because it converts client-side,
which is why this may go unnoticed.

**Fixes:**

1. Move `bin/ffmpeg` to `VCA/vca-without-azure/bin/ffmpeg` so both the
   `includeFiles` glob and `BASE_DIR` resolve. Costs 76 MB in the bundle.
2. Switch to `static-ffmpeg`: add it to `requirements.txt`, call
   `static_ffmpeg.add_paths()` in `main.py` as `api/index.py` already does, and
   delete the binary from the repository. Smaller repository, smaller bundle.
3. Accept WAV-only operation, remove `bin/ffmpeg` from `includeFiles`, and make
   the `400` message the documented behaviour. Since the UI converts
   client-side, this is a legitimate choice.

### Bundle size

`@vercel/python` functions have a size limit. Working against it:

- `bin/ffmpeg` — ~76 MB.
- `librosa` plus `numba`, `llvmlite`, `scikit-learn`, `scipy` — large.
- `pandas` — large, and **unused**.
- `textblob`, `requests`, `ffmpeg-python` — **unused**.

Dropping the four unused packages, and choosing `static-ffmpeg` or WAV-only over
the bundled binary, is the straightforward path to a comfortable margin.

### Function timeout

A multi-minute recording needs a Gemini upload, a Gemini generation call, a
`librosa.pyin` pass and a LanguageTool round trip. `pyin` is the slow local
stage and scales with duration × sample rate. Confirm the configured function
timeout exceeds your worst case, and note that `vercel.json` currently sets no
`maxDuration` — the plan default applies.

### Request body size

Serverless platforms cap request bodies at a few megabytes. The frontend's 3 MB
re-encode threshold exists for exactly this reason. Direct API clients must
respect the same budget — at 16 kHz mono 16-bit, roughly 90 seconds of audio per
megabyte.

### `api/index.py` cannot be imported

It calls `import static_ffmpeg`, which is not in `requirements.txt`. The module
is not referenced by `vercel.json`, so this is latent rather than active — but
anyone switching to Vercel's filesystem-based Python routing (where `api/*.py`
becomes an automatic entrypoint) will hit it immediately. Either add
`static-ffmpeg` to `requirements.txt` or delete the file.

### Cold starts

Every cold start re-imports librosa (slow), re-runs the Gemini readiness probe
(one API call), and creates a new log file. The readiness cache helps only
within one warm container's lifetime.

---

## 7.4 Alternative: container deployment

The pitfalls above are all consequences of serverless packaging. A container
sidesteps every one of them — system FFmpeg, a writable filesystem, no bundle
limit, no cold starts, and warm caching that actually persists.

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY VCA/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY VCA/vca-without-azure/ ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "vca_code.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t vca .
docker run -p 8000:8000 -e GEMINI_API_KEY=your_key vca
```

Because `VERCEL` is unset, `runtime_root` becomes the project directory inside
the container, which is writable. Mount a volume at `/app/json_output` and
`/app/log` if you want artifacts to survive container restarts — or add the
cleanup discussed in [06-configuration.md](06-configuration.md).

> Note: this Dockerfile is a worked suggestion, not a file present in the
> repository.

---

## 7.5 Pre-deployment checklist

- [ ] `GEMINI_API_KEY` set in the platform's environment variables
- [ ] Root Directory set to `VCA/vca-without-azure`
- [ ] `requirements.txt` reachable from the Root Directory
- [ ] FFmpeg strategy decided: bundled / `static-ffmpeg` / WAV-only
- [ ] Unused dependencies removed if bundle size is tight
- [ ] Function timeout exceeds worst-case analysis time
- [ ] `/health` returns `200`
- [ ] `/vca/analyze` succeeds with a real WAV file
- [ ] `/` serves the UI rather than the JSON fallback (confirms `includeFiles`)
- [ ] CORS origins narrowed if the API is not same-origin only
- [ ] A plan for `/tmp` artifact accumulation under sustained traffic
