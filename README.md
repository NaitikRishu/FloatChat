# FloatChat: ARGO Ocean Assistant

FloatChat is an AI-powered ocean analytics app for exploring ARGO float data through natural language. It combines a Python backend, structured ocean-profile storage, retrieval-based context, and a polished dashboard so users can ask ocean questions without digging through raw NetCDF files or specialist tools.

This project was built as an end-to-end portfolio piece: not just a model demo, but a complete application with ingestion, query planning, visualization, chat, testing, and deployment.

## Live Demo

- App: [https://floatchat-argo-assistant.onrender.com](https://floatchat-argo-assistant.onrender.com)
- Repository: [https://github.com/NaitikRishu/FloatChat](https://github.com/NaitikRishu/FloatChat)

## What It Does

- Seeds an Indian Ocean ARGO-style dataset with:
  - 20 floats
  - 780 profiles
  - 9,360 measurement rows
  - core and BGC-style variables
- Stores structured float, profile, and measurement data in SQLite.
- Retrieves metadata context for grounded responses.
- Translates natural-language questions into query plans and SQL-backed results.
- Visualizes outputs with:
  - an interactive basin map
  - profile charts
  - BGC comparison views
  - retrieval context
  - SQL trace panels
  - chatbot interaction

## Example Questions

- `Show me salinity profiles near the equator in March 2023`
- `Compare BGC parameters in the Arabian Sea for the last 6 months`
- `What are the nearest ARGO floats to 12.5, 72.4?`
- `What is salinity?`
- `What does BGC mean in Argo?`

## Architecture

### Backend

- Python application server
- SQLite for structured profile storage
- deterministic demo-data generator for ARGO-like floats
- lightweight retrieval layer for metadata matching
- rule-based plus optional LLM-assisted query planning

### Frontend

- HTML, CSS, and JavaScript
- interactive ocean map
- profile/comparison chart rendering
- chat-style assistant interface
- explainability panels for SQL and retrieval

### AI / Query Modes

The app supports multiple runtime modes:

- `Hugging Face`
  - recommended free-tier hosted option
- `Ollama`
  - local free model option
- `OpenAI`
  - optional hosted premium model path
- `Local fallback`
  - no external model required

If no external provider is configured, the app still works using the built-in local planner and response logic.

## Project Structure

```text
argo-ocean-assistant/
├── app/
│   ├── database.py
│   ├── demo_data.py
│   ├── ingest.py
│   ├── openai_service.py
│   ├── query_engine.py
│   └── server.py
├── static/
│   ├── app.js
│   ├── index.html
│   └── styles.css
├── tests/
│   └── test_app.py
├── Dockerfile
├── render.yaml
└── main.py
```

## Run Locally

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
python3 main.py --reset
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765).

## Configure an LLM Provider

### Option 1: Hugging Face

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
export LLM_PROVIDER="huggingface"
export HF_TOKEN="your_huggingface_token_here"
export LLM_MODEL="Qwen/Qwen2.5-7B-Instruct"
python3 main.py --reset
```

### Option 2: Ollama

```bash
ollama pull gemma3:4b
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
export LLM_PROVIDER="ollama"
export OLLAMA_MODEL="gemma3:4b"
python3 main.py --reset
```

### Option 3: OpenAI

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
export LLM_PROVIDER="openai"
export OPENAI_API_KEY="your_key_here"
export LLM_MODEL="gpt-5-mini"
python3 main.py --reset
```

## Run Tests

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
python3 -m unittest discover -s tests
python3 -m py_compile main.py app/*.py
```

## Deploy

### Docker

```bash
cd "/Users/naitikrishu/Documents/New project/argo-ocean-assistant"
docker build -t floatchat .
docker run -p 10000:10000 \
  -e LLM_PROVIDER="huggingface" \
  -e HF_TOKEN="your_huggingface_token_here" \
  -e LLM_MODEL="Qwen/Qwen2.5-7B-Instruct" \
  floatchat
```

Then open [http://127.0.0.1:10000](http://127.0.0.1:10000).

### Render

This repo already includes:

- [render.yaml](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/render.yaml)
- [Dockerfile](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/Dockerfile)

Deploy flow:

1. Push the repo to GitHub.
2. Create a Render web service from the repo.
3. Add `HF_TOKEN` as a secret environment variable.
4. Deploy.

## Resume-Ready Highlights

- Built a deployable conversational analytics platform for ARGO float data with Python, SQLite, interactive visualization, and natural-language query support.
- Designed a grounded query workflow that combines structured execution, metadata retrieval, explainable outputs, and optional LLM assistance.
- Shipped a full-stack portfolio app with ingestion, search, chat, charts, deployment config, and automated tests.

## Key Files

- App entry: [main.py](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/main.py)
- Query engine: [app/query_engine.py](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/app/query_engine.py)
- LLM integration: [app/openai_service.py](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/app/openai_service.py)
- Backend server: [app/server.py](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/app/server.py)
- Frontend UI: [static/index.html](/Users/naitikrishu/Documents/New project/argo-ocean-assistant/static/index.html)
