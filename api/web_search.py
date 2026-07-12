from __future__ import annotations

import json
import logging
from time import perf_counter
from urllib import error, parse, request

from api.web_search_history_store import (
    WebSearchHistoryEntry,
    create_web_search_history_entry,
    list_web_search_history_entries,
)
from api.schemas import WebSearchHit, WebSearchResponse
from api.settings import (
    SERPAPI_API_KEY,
    SERPAPI_ENABLED,
    SERPAPI_ENGINE,
    SERPAPI_NUM_RESULTS,
    SERPAPI_TIMEOUT_SEC,
    WEB_SEARCH_OPENAI_API_KEY,
    WEB_SEARCH_OPENAI_ENABLED,
    WEB_SEARCH_OPENAI_MODEL,
    WEB_SEARCH_OPENAI_TIMEOUT_SEC,
    WEB_SEARCH_OPENAI_URL,
)

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
logger = logging.getLogger("ai_knowledge_assistant.web_search")


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _normalize_snippet(result: dict) -> str:
    return (
        result.get("snippet")
        or result.get("snippet_highlighted_words", [""])[0]
        or result.get("rich_snippet", {}).get("top", {}).get("extensions", [""])[0]
        or ""
    )


def _log_web_search_failure(
    question: str,
    top_k: int,
    started_at: float,
    error_type: str,
    use_exception_trace: bool = False,
) -> None:
    log_method = logger.exception if use_exception_trace else logger.error
    log_method(
        "Web search request failed.",
        extra={
            "event": "web_search_request_failed",
            "context": {
                "question_length": len(question.strip()),
                "top_k": top_k,
                "engine": SERPAPI_ENGINE,
                "latency_ms": int((perf_counter() - started_at) * 1000),
                "error_type": error_type,
            },
        },
    )


def _record_web_search_history(
    *,
    question: str,
    top_k: int,
    status: str,
    hit_count: int,
    latency_ms: int,
    error_type: str,
) -> None:
    create_web_search_history_entry(
        question_length=len(question.strip()),
        top_k=top_k,
        engine=SERPAPI_ENGINE,
        status=status,
        hit_count=hit_count,
        latency_ms=latency_ms,
        updated_at=_utc_now_iso(),
        error_type=error_type,
    )


def get_web_search_history(limit: int = 20) -> tuple[WebSearchHistoryEntry, ...]:
    return list_web_search_history_entries(limit=limit)


def _openai_web_search(question: str, top_k: int) -> WebSearchResponse:
    payload = {
        "model": WEB_SEARCH_OPENAI_MODEL,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a web search assistant. Return only valid JSON with a top-level 'hits' array. "
                    "Each hit must contain title, link, snippet, source, and position."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Search the web for: {question}\n"
                    f"Return up to {top_k} relevant results as JSON."
                ),
            },
        ],
        "response_format": {"type": "json_object"},
    }
    req = request.Request(
        url=WEB_SEARCH_OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {WEB_SEARCH_OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=WEB_SEARCH_OPENAI_TIMEOUT_SEC) as response:
        body = response.read().decode("utf-8")
    data = json.loads(body)
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    hits = [
        WebSearchHit(
            title=str(item.get("title", "")).strip(),
            link=str(item.get("link", "")).strip(),
            snippet=str(item.get("snippet", "")).strip(),
            source=str(item.get("source", "openai")).strip() or "openai",
            position=index,
        )
        for index, item in enumerate(parsed.get("hits", [])[:top_k], start=1)
        if str(item.get("title", "")).strip() and str(item.get("link", "")).strip()
    ]
    return WebSearchResponse(
        question=question,
        top_k=top_k,
        engine="openai-compatible",
        hits=hits,
    )


def _serpapi_web_search(question: str, top_k: int) -> WebSearchResponse:
    if not SERPAPI_ENABLED:
        raise ValueError("SerpAPI integration is disabled. Set SERPAPI_ENABLED=true.")
    if not SERPAPI_API_KEY.strip():
        raise ValueError("SERPAPI_API_KEY is missing.")

    query = parse.urlencode(
        {
            "engine": SERPAPI_ENGINE,
            "q": question,
            "api_key": SERPAPI_API_KEY,
            "num": min(top_k, SERPAPI_NUM_RESULTS),
        }
    )
    url = f"{SERPAPI_ENDPOINT}?{query}"

    with request.urlopen(url, timeout=SERPAPI_TIMEOUT_SEC) as response:
        body = response.read().decode("utf-8")

    payload = json.loads(body)
    organic_results = payload.get("organic_results", [])
    hits = [
        WebSearchHit(
            title=result.get("title", ""),
            link=result.get("link", ""),
            snippet=_normalize_snippet(result),
            source="serpapi",
            position=result.get("position", index),
        )
        for index, result in enumerate(organic_results[:top_k], start=1)
        if result.get("title") and result.get("link")
    ]

    return WebSearchResponse(
        question=question,
        top_k=top_k,
        engine=SERPAPI_ENGINE,
        hits=hits,
    )


def web_search(question: str, top_k: int) -> WebSearchResponse:
    started_at = perf_counter()
    try:
        if WEB_SEARCH_OPENAI_ENABLED and WEB_SEARCH_OPENAI_URL and WEB_SEARCH_OPENAI_API_KEY.strip():
            response = _openai_web_search(question=question, top_k=top_k)
        else:
            response = _serpapi_web_search(question=question, top_k=top_k)
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        if WEB_SEARCH_OPENAI_ENABLED and WEB_SEARCH_OPENAI_URL and WEB_SEARCH_OPENAI_API_KEY.strip():
            try:
                response = _serpapi_web_search(question=question, top_k=top_k)
            except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as fallback_exc:
                latency_ms = int((perf_counter() - started_at) * 1000)
                _record_web_search_history(
                    question=question,
                    top_k=top_k,
                    status="failed",
                    hit_count=0,
                    latency_ms=latency_ms,
                    error_type=type(fallback_exc).__name__,
                )
                _log_web_search_failure(
                    question=question,
                    top_k=top_k,
                    started_at=started_at,
                    error_type=type(fallback_exc).__name__,
                    use_exception_trace=True,
                )
                raise ValueError("Failed to fetch results from OpenAI-compatible web search and SerpAPI.") from fallback_exc
        else:
            latency_ms = int((perf_counter() - started_at) * 1000)
            _record_web_search_history(
                question=question,
                top_k=top_k,
                status="failed",
                hit_count=0,
                latency_ms=latency_ms,
                error_type=type(exc).__name__,
            )
            _log_web_search_failure(
                question=question,
                top_k=top_k,
                started_at=started_at,
                error_type=type(exc).__name__,
                use_exception_trace=True,
            )
            raise ValueError("Failed to fetch web search results.") from exc

    latency_ms = int((perf_counter() - started_at) * 1000)
    _record_web_search_history(
        question=question,
        top_k=top_k,
        status="completed",
        hit_count=len(response.hits),
        latency_ms=latency_ms,
        error_type="",
    )
    logger.info(
        "Web search request completed.",
        extra={
            "event": "web_search_request_completed",
            "context": {
                "question_length": len(question.strip()),
                "top_k": top_k,
                "engine": response.engine,
                "hit_count": len(response.hits),
                "latency_ms": latency_ms,
            },
        },
    )
    return response
