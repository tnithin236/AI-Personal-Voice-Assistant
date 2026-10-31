"""Key-less web search through the `ddgs` package (DuckDuckGo etc.)."""
import logging

from .base import ToolError

log = logging.getLogger(__name__)


def web_search(query: str, max_results: int = 5) -> str:
    if not (query or "").strip():
        raise ToolError("What should I search for?")
    try:
        from ddgs import DDGS
    except ImportError as e:
        raise ToolError("Web search needs the 'ddgs' package (pip install ddgs).") from e
    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception as e:  # noqa: BLE001 - network / rate limit errors vary
        log.warning("web search failed: %s", e)
        raise ToolError(f"Web search failed (are you online?): {e}") from e
    if not results:
        return f"No web results for '{query}'."
    lines = []
    for i, r in enumerate(results, 1):
        body = " ".join((r.get("body") or "").split())[:240]
        lines.append(f"[{i}] {r.get('title', '').strip()} - {body} ({r.get('href', '')})")
    return "\n".join(lines)
