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

For protected admin actions in the UI, also set:

```bash
ADMIN_USERNAME=owner
ADMIN_PASSWORD=change_me_admin_password
ADMIN_SESSION_SECRET=change_me_session_secret
```

Without `ADMIN_PASSWORD`, the assistant stays public, but `Documents` and `System` remain read-only preview areas and protected actions stay disabled.

## Docker Swarm Run

This repository now includes a more production-like swarm-compatible stack for the `FastAPI` app and `PostgreSQL + pgvector`.

Files:

- `Dockerfile`
- `docker-stack.yml`
- `.env.swarm.example`
- `docker/app/entrypoint.sh`
- `docker/postgres/init/01-init.sql`

Prepare the swarm environment file:

```bash
cp .env.swarm.example .env.swarm
set -a
source .env.swarm
set +a
```

Create the required Docker secret for the database password:

```bash
printf 'change_me_super_secret_password' | docker secret create "${POSTGRES_PASSWORD_SECRET}" -
```

Build the application image first:

```bash
docker build -t ai-knowledge-assistant:local .
```

Initialize swarm on the local machine if needed:

```bash
docker swarm init
```

Deploy the stack:

```bash
docker stack deploy -c docker-stack.yml ai-knowledge-assistant
```

Check services:

```bash
docker stack services ai-knowledge-assistant
docker stack ps ai-knowledge-assistant
```

Inspect logs:

```bash
docker service logs -f ai-knowledge-assistant_app
docker service logs -f ai-knowledge-assistant_db
```

Open the app:

```text
http://localhost:8000
```

Remove the stack:

```bash
docker stack rm ai-knowledge-assistant
```

Notes:

- the stack runs the app with `CHUNK_STORAGE_BACKEND=pgvector`;
- the database service uses a `pgvector`-enabled Postgres image and creates `EXTENSION vector` on first initialization;
- the app reads database credentials through `POSTGRES_PASSWORD_FILE` and supports `*_FILE` secrets for app settings as well;
- the app waits for the database before starting `uvicorn`;
- `deploy.resources` and `deploy.restart_policy` are already set with conservative defaults;
- `APP_REPLICAS=1` is the safe default because uploads currently write to local app data volume; raise replicas only if you move uploads/raw corpus to shared storage;
- `DB_REPLICAS=1` should stay as-is unless you introduce a real HA/replication strategy for PostgreSQL;
- Docker daemon must be running before `docker build` or `docker stack deploy`.

Recommended production-like knobs in `.env.swarm`:

```bash
APP_IMAGE=ai-knowledge-assistant:local
APP_PORT=8000
APP_REPLICAS=1
APP_CPU_RESERVATION=0.25
APP_CPU_LIMIT=1.00
APP_MEMORY_RESERVATION=256M
APP_MEMORY_LIMIT=1G
UVICORN_WORKERS=1

DB_IMAGE=pgvector/pgvector:pg16
DB_REPLICAS=1
DB_CPU_RESERVATION=0.25
DB_CPU_LIMIT=1.00
DB_MEMORY_RESERVATION=256M
DB_MEMORY_LIMIT=1G

POSTGRES_DB=ai_knowledge_assistant
POSTGRES_USER=postgres
POSTGRES_SSL_MODE=disable
POSTGRES_PASSWORD_SECRET=ai_knowledge_assistant_postgres_password
```

Optional application secrets:

- `LLM_API_KEY_FILE`
- `SERPAPI_API_KEY_FILE`

The app now supports the `*_FILE` pattern in settings, so these values can come from Docker secrets if you later extend the stack with provider-specific secrets.

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
