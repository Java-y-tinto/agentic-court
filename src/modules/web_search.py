# Host-side web search. Boundary tools execute in the governance layer, never in
# the sandbox, so the API key stays on the host (credential blindness). Egress is
# bounded here by hard controls — search-only, rate-limited, logged — rather than
# by a per-call approval prompt. The backend is pluggable (Tavily today; SearXNG
# or DuckDuckGo are drop-in replacements behind SearchClient).

import os
from contextvars import ContextVar
from typing import Any, Protocol

from .logger import logger


class SearchClient(Protocol):
    """Minimal interface WebSearch needs from a search backend."""

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]: ...


class WebSearchNotActive(RuntimeError):
    pass


# ContextVar (mirrors the sandbox) so concurrent sessions don't share a counter.
_active: ContextVar["WebSearch | None"] = ContextVar("active_web_search", default=None)


def get_active_search() -> "WebSearch":
    web_search = _active.get()
    if web_search is None:
        raise WebSearchNotActive("No web search session is active")
    return web_search


class WebSearch:
    """Per-session web search with egress controls. Inject `client` for tests;
    otherwise a Tavily client is built from TAVILY_API_KEY (None if unset, which
    degrades to a clear 'unavailable' message rather than crashing the session)."""

    def __init__(
        self,
        max_searches: int = 10,
        *,
        client: SearchClient | None = None,
        max_results: int = 5,
    ):
        self._max_searches = max_searches
        self._max_results = max_results
        self._count = 0
        self._client = client if client is not None else _build_tavily_client()

    def search(self, query: str) -> str:
        if self._client is None:
            return "Web search is unavailable: TAVILY_API_KEY is not configured."
        if self._count >= self._max_searches:
            return f"Web search budget exhausted ({self._max_searches} searches per session)."
        self._count += 1
        logger.info("[WebSearch] (%d/%d) query=%r", self._count, self._max_searches, query)
        try:
            response = self._client.search(query, max_results=self._max_results)
        except Exception as exc:  # external API boundary
            logger.warning("[WebSearch] query failed: %s", exc)
            return f"Web search failed: {exc}"
        return _format_results(response)

    def __enter__(self) -> "WebSearch":
        self._token = _active.set(self)
        return self

    def __exit__(self, *exc: object) -> bool:
        _active.reset(self._token)
        return False


def _build_tavily_client() -> SearchClient | None:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    from tavily import TavilyClient

    return TavilyClient(api_key=api_key)


def _format_results(response: dict[str, Any]) -> str:
    results = response.get("results", []) if isinstance(response, dict) else []
    if not results:
        return "No results."
    blocks = []
    for item in results:
        title = item.get("title", "(untitled)")
        url = item.get("url", "")
        content = item.get("content", "").strip()
        blocks.append(f"- {title} ({url})\n  {content}")
    return "\n".join(blocks)
