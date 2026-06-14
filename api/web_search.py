from __future__ import annotations

import json
import logging
from time import perf_counter
from urllib import error, parse, request

from api.schemas import WebSearchHit, WebSearchResponse
from api.settings import (
    SERPAPI_API_KEY,
    SERPAPI_ENABLED,
    SERPAPI_ENGINE,
    SERPAPI_NUM_RESULTS,
    SERPAPI_TIMEOUT_SEC,
)

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
logger = logging.getLogger("ai_knowledge_assistant.web_search")


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


def web_search(question: str, top_k: int) -> WebSearchResponse:
    started_at = perf_counter()
    if not SERPAPI_ENABLED:
        _log_web_search_failure(
            question=question,
            top_k=top_k,
            started_at=started_at,
            error_type="ValueError",
        )
        raise ValueError("SerpAPI integration is disabled. Set SERPAPI_ENABLED=true.")
    if not SERPAPI_API_KEY.strip():
        _log_web_search_failure(
            question=question,
            top_k=top_k,
            started_at=started_at,
            error_type="ValueError",
        )
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

    try:
        with request.urlopen(url, timeout=SERPAPI_TIMEOUT_SEC) as response:
            body = response.read().decode("utf-8")
    except (error.HTTPError, error.URLError, TimeoutError) as exc:
        _log_web_search_failure(
            question=question,
            top_k=top_k,
            started_at=started_at,
            error_type=type(exc).__name__,
            use_exception_trace=True,
        )
        raise ValueError("Failed to fetch results from SerpAPI.") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        _log_web_search_failure(
            question=question,
            top_k=top_k,
            started_at=started_at,
            error_type=type(exc).__name__,
            use_exception_trace=True,
        )
        raise ValueError("Invalid response from SerpAPI.") from exc

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

    response = WebSearchResponse(
        question=question,
        top_k=top_k,
        engine=SERPAPI_ENGINE,
        hits=hits,
    )
    logger.info(
        "Web search request completed.",
        extra={
            "event": "web_search_request_completed",
            "context": {
                "question_length": len(question.strip()),
                "top_k": top_k,
                "engine": SERPAPI_ENGINE,
                "hit_count": len(hits),
                "latency_ms": int((perf_counter() - started_at) * 1000),
            },
        },
    )
    return response
