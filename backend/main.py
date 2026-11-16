"""Vaani backend entry point.   Run from the project root:  uvicorn backend.main:app --port 8000"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.core.logging_setup import setup_logging
from backend.services import get_services

log = logging.getLogger("vaani")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_services()
    setup_logging(s.cfg.logs_dir)
    log.info("Vaani starting | model=%s | data=%s", s.settings.get("llm_model"), s.cfg.data_dir)
    warm = [asyncio.create_task(s.llm.warm()),
            asyncio.create_task(asyncio.to_thread(_warm_embedder, s)),
            asyncio.create_task(asyncio.to_thread(s.tts.piper.warm, s.settings.get("piper_voice")))]
    yield
    for t in warm:
        t.cancel()
    s.close()
    log.info("Vaani stopped")


def _warm_embedder(s) -> None:
    try:
        s.embedder.embed(["warm-up"])
        _ = s.vectors  # open the vector database now so the first chat message does not pay for it
    except Exception as e:  # noqa: BLE001
        log.warning("Embedding/vector-store warm-up skipped: %s", e)


app = FastAPI(title="Vaani - Personal Voice Assistant", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_services().cfg.allowed_origins,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Language"])
app.include_router(router)


@app.get("/")
def root():
    return {"app": "Vaani", "docs": "/docs", "health": "/api/health"}
