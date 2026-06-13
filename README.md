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
export LLM_ENABLED=true
export LLM_API_KEY=your_api_key
export LLM_MODEL=gpt-4o-mini
export LLM_API_BASE=https://api.openai.com/v1
```

If LLM settings are missing or the request fails, the app falls back to the local grounded extractive answer.
