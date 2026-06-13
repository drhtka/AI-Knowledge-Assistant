# AI Knowledge Assistant

Production-like `RAG` scaffold in the same style as `anti_fraud_analytics_platform`.

## Goal

Show one compact but credible project with:

- `FastAPI` backend;
- retrieval and grounded answers;
- lightweight server-rendered UI;
- clear repo layout for further ingestion, embeddings, and evaluation work.

## Structure

- `api/` - app, schemas, retrieval baseline.
- `data/` - local corpora and eval sets.
- `notebooks/` - experiments.
- `scripts/` - helper scripts.
- `src/` - future pipeline modules.
- `templates/` - HTML UI.
- `static/` - CSS and JS.

## Endpoints

- `GET /health`
- `POST /search`
- `POST /web-search`
- `POST /ask`
- `GET /`

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.app:app --reload
```

## Optional LLM Mode

Enable LLM-backed grounded answers with environment variables:

```bash
cp .env.example .env
set -a
source .env
set +a
```

If LLM settings are missing or the request fails, the app falls back to the local grounded extractive answer.

## Optional SerpAPI Web Search

Use SerpAPI as a separate external retrieval source:

```bash
cp .env.example .env
set -a
source .env
set +a
```

Required variables for web search:

```bash
SERPAPI_ENABLED=true
SERPAPI_API_KEY=your_serpapi_key
SERPAPI_ENGINE=google
SERPAPI_NUM_RESULTS=5
SERPAPI_TIMEOUT_SEC=15
```

This integration is separate from LLM generation. It is meant for external web retrieval through `POST /web-search`.
