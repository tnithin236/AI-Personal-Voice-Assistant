"""Async client for Ollama's local HTTP API (streaming chat + JSON mode)."""
import json
import logging
import re
from typing import AsyncIterator

import httpx

log = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLM:
    def __init__(self, cfg, settings):
        self.cfg, self.settings = cfg, settings
        self.last_stats: dict = {}

    def _options(self, **override) -> dict:
        s = self.settings.all()
        opts = {"num_ctx": int(s["num_ctx"]), "temperature": float(s["temperature"]),
                "num_predict": int(s["max_tokens"])}
        if int(s["num_gpu"]) >= 0:
            opts["num_gpu"] = int(s["num_gpu"])
        opts.update(override)
        return opts

    def _payload(self, messages, stream: bool, options: dict, fmt: str | None = None) -> dict:
        p = {"model": self.settings.get("llm_model"), "messages": messages, "stream": stream,
             "options": options, "keep_alive": self.cfg.keep_alive}
        if fmt:
            p["format"] = fmt
        return p

    async def stream(self, messages: list[dict], options: dict | None = None) -> AsyncIterator[str]:
        payload = self._payload(messages, True, self._options(**(options or {})))
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=5)) as client:
                async with client.stream("POST", f"{self.cfg.ollama_url}/api/chat", json=payload) as r:
                    if r.status_code != 200:
                        body = (await r.aread()).decode("utf-8", "replace")[:300]
                        raise LLMError(f"Ollama returned {r.status_code}: {body}")
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        d = json.loads(line)
                        if d.get("error"):
                            raise LLMError(d["error"])
                        tok = d.get("message", {}).get("content", "")
                        if tok:
                            yield tok
                        if d.get("done"):
                            self.last_stats = {k: d.get(k) for k in (
                                "eval_count", "eval_duration", "prompt_eval_count",
                                "prompt_eval_duration", "load_duration", "total_duration")}
        except httpx.ConnectError as e:
            raise LLMError(f"Cannot reach Ollama at {self.cfg.ollama_url}. Is it running? (try: ollama serve)") from e
        except httpx.TimeoutException as e:
            raise LLMError("Ollama timed out.") from e

    async def chat_json(self, messages: list[dict], options: dict | None = None) -> dict:
        payload = self._payload(messages, False, self._options(**(options or {})), fmt="json")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=5)) as client:
                r = await client.post(f"{self.cfg.ollama_url}/api/chat", json=payload)
            if r.status_code != 200:
                raise LLMError(f"Ollama returned {r.status_code}: {r.text[:300]}")
            raw = r.json().get("message", {}).get("content", "")
        except httpx.ConnectError as e:
            raise LLMError(f"Cannot reach Ollama at {self.cfg.ollama_url}.") from e
        return parse_json_loose(raw)

    async def models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{self.cfg.ollama_url}/api/tags")
            r.raise_for_status()
        return sorted(m["name"] for m in r.json().get("models", []))

    async def running(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{self.cfg.ollama_url}/api/ps")
            r.raise_for_status()
        return r.json().get("models", [])

    async def health(self) -> dict:
        try:
            names = await self.models()
            want = self.settings.get("llm_model")
            return {"ok": True, "model": want, "model_available": want in names, "models": names}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    async def warm(self) -> None:
        """Load the model into memory so the first real request is fast."""
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                await client.post(f"{self.cfg.ollama_url}/api/generate", json={
                    "model": self.settings.get("llm_model"), "prompt": "", "keep_alive": self.cfg.keep_alive,
                    "options": {k: v for k, v in self._options().items() if k in ("num_ctx", "num_gpu")}})
            log.info("LLM warmed up")
        except Exception as e:  # noqa: BLE001
            log.warning("LLM warm-up skipped: %s", e)


def parse_json_loose(raw: str) -> dict:
    """Parse model output as JSON, tolerating code fences and surrounding text."""
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return {}
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}
    return obj if isinstance(obj, dict) else {}
