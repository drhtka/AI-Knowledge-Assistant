# AI Knowledge Assistant

Portfolio-ready `RAG` project with local document ingestion, configurable retrieval, grounded answering, evaluation scripts, and a lightweight demo UI.

## What It Does

This project shows a compact but realistic knowledge assistant workflow:

- loads local `txt` and `md` documents;
- splits them into chunks and stores processed artifacts;
- retrieves relevant chunks with `TF-IDF` or embeddings;
- generates grounded answers from retrieved context;
- exposes retrieval controls through API and UI;
- evaluates retrieval quality and stores experiment reports.

## Tech Stack

- `Python`
- `FastAPI`
- `Pydantic`
- `Jinja2` templates
- vanilla `JavaScript` and `CSS`
- `scikit-learn` for `TF-IDF`
- `sentence-transformers` for embeddings baseline

## Key Features

- local ingestion pipeline for `txt` and `md` documents
- processed chunk storage in `data/processed/chunks.jsonl`
- retrieval modes: `auto`, `tfidf`, `embeddings`
- grounded answer generation with safe fallback behavior
- optional OpenAI-compatible LLM integration
- separate external web search via `SerpAPI`
- evaluation dataset, metrics, report history, and report comparison
- demo UI with retrieval mode switch, chunking preset switch, document upload, and mode comparison

## What I Implemented Myself

- local document ingestion and processed chunk pipeline
- retrieval baseline evolution from simple search to `TF-IDF` and embeddings
- grounded answer flow with confidence and fallback behavior
- evaluation scripts for metrics, chunking experiments, and saved report comparison
- API controls for retrieval mode and chunking presets
- server-rendered demo UI for asking questions, uploading documents, and comparing modes

## Project Structure

- `api/` - backend app, schemas, retrieval, generation, ingestion
- `data/` - raw corpus, processed chunks, eval dataset, saved reports
- `scripts/` - evaluation and experiment helper scripts
- `templates/` - HTML UI
- `static/` - CSS and JavaScript
- `src/` - reserved for future pipeline modules

## Endpoints

- `GET /`
- `GET /health`
- `POST /ingest`
- `POST /search`
- `POST /ask`
- `POST /web-search`
- `GET /chunking-config`
- `POST /chunking-config`

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.app:app --reload
```

## Optional Environment Setup

```bash
cp .env.example .env
set -a
source .env
set +a
```

If optional services are not configured, the app keeps working with the local baseline.

## Optional LLM Mode

The project supports OpenAI-compatible grounded answer generation through environment variables.

If LLM settings are missing or a request fails, the app falls back to the local grounded extractive answer.

## Optional SerpAPI Web Search

Use `SerpAPI` as a separate external retrieval source:

```bash
SERPAPI_ENABLED=true
SERPAPI_API_KEY=your_serpapi_key
SERPAPI_ENGINE=google
SERPAPI_NUM_RESULTS=5
SERPAPI_TIMEOUT_SEC=15
```

This integration is intentionally separate from local retrieval and can be demonstrated through `POST /web-search` and the UI web search block.
