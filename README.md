# ARGO Ocean Assistant

ARGO Ocean Assistant is a resume-ready ocean analytics app with a real web UI, structured storage, natural-language querying, and optional live LLM support. It is designed to feel like a real product demo rather than a notebook prototype.

## What it does

- Seeds an Indian Ocean ARGO-style catalog with:
  - 20 floats
  - 780 profiles
  - 9,360 measurement rows
  - core and BGC-style variables
- Stores data in SQLite and indexes metadata for retrieval.
- Accepts natural-language questions like:
  - `Show me salinity profiles near the equator in March 2023`
  - `Compare BGC parameters in the Arabian Sea for the last 6 months`
  - `What are the nearest ARGO floats to 12.5, 72.4?`
- Shows:
  - interactive basin map
  - profile and comparison charts
  - SQL trace
  - retrieval grounding
  - AI mode status

## AI modes

The app now supports four execution modes:

- `Hugging Face free-tier mode`
  - recommended for a low-cost or free demo path
  - enabled when `LLM_PROVIDER=huggingface` and `HF_TOKEN` is set
  - uses the Hugging Face OpenAI-compatible router
- `Ollama local-free mode`
  - runs a local model on your machine
  - enabled when `LLM_PROVIDER=ollama`
  - no paid API required
- `OpenAI live mode`
  - still supported if you want a stronger hosted model
  - enabled when `LLM_PROVIDER=openai` and `OPENAI_API_KEY` is set
- `Local fallback mode`
  - works with no API key
  - uses the built-in rule-based planner and answer generator

This means the app is always runnable, but now it can use genuinely free options instead of assuming paid usage.

## Local run

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
python3 main.py --reset
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765).

## Run with Hugging Face free tier

Copy the env template and use the free-tier configuration:

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
cp .env.example .env
export LLM_PROVIDER="huggingface"
export HF_TOKEN="your_huggingface_token_here"
export LLM_MODEL="Qwen/Qwen2.5-7B-Instruct"
export LLM_REASONING_EFFORT="low"
python3 main.py --reset
```

When the app boots, the top bar will show whether it is in `Hugging Face live`, `Ollama live`, or `Local fallback` mode.

## Run with Ollama locally for free

Start Ollama and pull a small model:

```bash
ollama pull gemma3:4b
```

Then run the app:

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
export LLM_PROVIDER="ollama"
export OLLAMA_MODEL="gemma3:4b"
python3 main.py --reset
```

## Run with OpenAI

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
export LLM_PROVIDER="openai"
export OPENAI_API_KEY="your_key_here"
export LLM_MODEL="gpt-5-mini"
python3 main.py --reset
```

## Test

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
python3 -m unittest discover -s tests
python3 -m py_compile main.py app/*.py
```

## Deploy

### Option 1: Docker

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
docker build -t argo-ocean-assistant .
docker run -p 10000:10000 \
  -e LLM_PROVIDER="huggingface" \
  -e HF_TOKEN="your_huggingface_token_here" \
  -e LLM_MODEL="Qwen/Qwen2.5-7B-Instruct" \
  argo-ocean-assistant
```

Then open [http://127.0.0.1:10000](http://127.0.0.1:10000).

### Option 2: Render

This repo includes a ready-to-use [render.yaml](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/render.yaml) and [Dockerfile](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/Dockerfile).

Deploy steps:

1. Push this folder to GitHub.
2. Create a new Render web service from the repo.
3. Render will detect `render.yaml`.
4. Add `HF_TOKEN` in the Render environment settings.
5. Deploy.

Important:
- I prepared the deployment config, but I cannot complete the actual cloud deployment from this local workspace because that needs your hosting account and API credentials.

## Files worth showing on your resume or portfolio

- App entry: [main.py](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/main.py)
- Query engine: [app/query_engine.py](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/app/query_engine.py)
- LLM integration: [app/openai_service.py](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/app/openai_service.py)
- Web server: [app/server.py](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/app/server.py)
- Frontend: [static/index.html](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/static/index.html)

## Suggested resume bullets

- Built a deployable ARGO ocean analytics assistant with Python, SQLite, natural-language querying, and an interactive geospatial dashboard.
- Integrated free-tier and local LLM providers into a grounded analytics workflow for query planning and answer generation with deterministic SQL execution.
- Designed a responsive frontend for float exploration, retrieval transparency, profile comparison, and explainable AI-assisted ocean data discovery.
