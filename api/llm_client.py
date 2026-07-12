from __future__ import annotations

import json
from urllib import error, request

from api.settings import (
    LLM_API_BASE,
    LLM_API_KEY,
    LLM_CHAT_COMPLETIONS_URL,
    LLM_ENABLED,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TIMEOUT_SEC,
)


def generate_answer_from_context(question: str, context: str) -> str | None:
    if not LLM_ENABLED or not LLM_API_KEY.strip():
        return None

    endpoint = LLM_CHAT_COMPLETIONS_URL or f"{LLM_API_BASE}/chat/completions"
    payload = {
        "model": LLM_MODEL,
        "temperature": 0.2,
        "max_tokens": LLM_MAX_TOKENS,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a grounded RAG assistant. Answer only using the provided context. "
                    "If context is insufficient, clearly say it."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Context:\n{context}\n\n"
                    "Return a concise answer and do not add unsupported claims."
                ),
            },
        ],
    }

    req = request.Request(
        url=endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=LLM_TIMEOUT_SEC) as response:
            body = response.read().decode("utf-8")
    except (error.HTTPError, error.URLError, TimeoutError):
        return None

    try:
        data = json.loads(body)
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None
