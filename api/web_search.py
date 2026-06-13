from __future__ import annotations

import json
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


def _normalize_snippet(result: dict) -> str:
    return (
        result.get("snippet")
        or result.get("snippet_highlighted_words", [""])[0]
        or result.get("rich_snippet", {}).get("top", {}).get("extensions", [""])[0]
        or ""
    )


def web_search(question: str, top_k: int) -> WebSearchResponse:
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

    try:
        with request.urlopen(url, timeout=SERPAPI_TIMEOUT_SEC) as response:
            body = response.read().decode("utf-8")
    except (error.HTTPError, error.URLError, TimeoutError) as exc:
        raise ValueError("Failed to fetch results from SerpAPI.") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
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

    return WebSearchResponse(
        question=question,
        top_k=top_k,
        engine=SERPAPI_ENGINE,
        hits=hits,
    )
