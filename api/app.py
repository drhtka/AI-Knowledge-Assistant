from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.retrieval import ask, search
from api.schemas import AskRequest, AskResponse, HealthResponse, SearchRequest, SearchResponse
from api.settings import STATIC_DIR, TEMPLATES_DIR


app = FastAPI(
    title="AI Knowledge Assistant API",
    version="0.1.0",
    description="Compact scaffold for a production-like RAG portfolio project.",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

DEMO_PROMPTS = [
    {
        "label": "Architecture",
        "question": "What layers should a production-like RAG system have?",
    },
    {
        "label": "Evaluation",
        "question": "How should I evaluate retrieval quality in a RAG system?",
    },
    {
        "label": "Hybrid Search",
        "question": "Why does hybrid retrieval help compared to embeddings only?",
    },
]


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    question = request.query_params.get("question", "")
    top_k_raw = request.query_params.get("top_k", "3") or "3"
    top_k = max(1, min(10, int(top_k_raw)))

    search_result = search(question, top_k) if question else None
    ask_result = ask(question, top_k) if question else None

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page_title": "AI Knowledge Assistant",
            "question": question,
            "top_k": top_k,
            "demo_prompts": DEMO_PROMPTS,
            "search_result": search_result,
            "ask_result": ask_result,
            "search_result_json": search_result.model_dump(mode="json") if search_result else {},
            "ask_result_json": ask_result.model_dump(mode="json") if ask_result else {},
        },
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", ready=True, project="ai_knowledge_assistant")


@app.post("/search", response_model=SearchResponse)
def search_endpoint(request: SearchRequest) -> SearchResponse:
    return search(question=request.question, top_k=request.top_k)


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(request: AskRequest) -> AskResponse:
    return ask(question=request.question, top_k=request.top_k)
