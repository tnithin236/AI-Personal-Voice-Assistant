"""WebSocket protocol (JSON).

client -> server: chat{text,conversation_id?} | regenerate{conversation_id} | voice_start | voice_stop |
                  voice_cancel | cancel | ping
server -> client: conversation{id} | status{stage} | level{value} | transcript{text,language} | token{text} |
                  tool{tool,result} | pending_action{id,tool,description} | done{...} | error{message} | cancelled
"""
import asyncio
import json
import logging
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services import get_services

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    s = get_services()
    send_lock = asyncio.Lock()
    state: dict = {"task": None, "level": None}

    async def emit(ev: dict):
        async with send_lock:
            await ws.send_json(ev)

    async def guarded(coro_fn):
        try:
            await coro_fn()
        except asyncio.CancelledError:
            with suppress(Exception):
                await emit({"type": "cancelled"})
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("pipeline error")
            with suppress(Exception):
                await emit({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            with suppress(Exception):
                await emit({"type": "status", "stage": "idle"})

    def start_task(coro_fn):
        if state["task"] and not state["task"].done():
            state["task"].cancel()
        state["task"] = asyncio.create_task(guarded(coro_fn))

    async def resolve_conversation(cid):
        cid, created = s.ensure_conversation(cid)
        if created:
            await emit({"type": "conversation", "id": cid})
        return cid

    async def level_loop():
        while True:
            await emit({"type": "level", "value": min(1.0, s.recorder.level * 8)})
            await asyncio.sleep(0.08)

    def stop_level():
        if state["level"]:
            state["level"].cancel()
            state["level"] = None

    async def voice_pipeline(audio, cid_in):
        cfg = s.settings.all()
        await emit({"type": "status", "stage": "transcribing"})
        lang = cfg["language"] if cfg["language"] in ("en", "ta") else None
        result = await asyncio.to_thread(s.stt.transcribe, audio, cfg["whisper_model"], lang)
        if not result["text"]:
            await emit({"type": "error", "message": "I didn't catch that. Hold the button while you speak."})
            return
        cid = await resolve_conversation(cid_in)
        await emit({"type": "transcript", "text": result["text"], "language": result["language"],
                    "stt_ms": result["ms"]})
        await s.agent.respond(cid, result["text"], emit, stt_lang=result["language"])

    try:
        while True:
            try:
                msg = json.loads(await ws.receive_text())
            except json.JSONDecodeError:
                await emit({"type": "error", "message": "Invalid JSON"})
                continue
            kind = msg.get("type")

            if kind == "chat":
                text = (msg.get("text") or "").strip()
                if text:
                    async def run_chat(text=text, cid_in=msg.get("conversation_id")):
                        cid = await resolve_conversation(cid_in)
                        await s.agent.respond(cid, text, emit)
                    start_task(run_chat)

            elif kind == "regenerate":
                cid = msg.get("conversation_id")
                text = s.convo.last_user_text(cid) if cid else None
                if text:
                    s.convo.delete_last_assistant(cid)
                    start_task(lambda cid=cid, text=text: s.agent.respond(cid, text, emit, save_user=False))

            elif kind == "voice_start":
                if s.recorder.recording:
                    continue
                try:
                    await asyncio.to_thread(s.recorder.start, s.settings.get("mic_device"))
                except Exception as e:  # noqa: BLE001
                    await emit({"type": "error", "message": f"Microphone error: {e}"})
                    continue
                await emit({"type": "status", "stage": "listening"})
                state["level"] = asyncio.create_task(level_loop())
                model = s.settings.get("whisper_model")  # preload Whisper while the user speaks
                asyncio.create_task(asyncio.to_thread(s.stt.ensure_loaded, model))

            elif kind == "voice_stop":
                stop_level()
                if not s.recorder.recording:
                    continue
                audio = await asyncio.to_thread(s.recorder.stop)
                cid_in = msg.get("conversation_id")
                start_task(lambda audio=audio, cid_in=cid_in: voice_pipeline(audio, cid_in))

            elif kind == "voice_cancel":
                stop_level()
                if s.recorder.recording:
                    await asyncio.to_thread(s.recorder.stop)
                await emit({"type": "status", "stage": "idle"})

            elif kind == "cancel":
                stop_level()
                if s.recorder.recording:
                    await asyncio.to_thread(s.recorder.stop)
                if state["task"] and not state["task"].done():
                    state["task"].cancel()
                else:
                    await emit({"type": "status", "stage": "idle"})

            elif kind == "ping":
                await emit({"type": "pong"})

    except WebSocketDisconnect:
        log.info("WebSocket disconnected")
    finally:
        stop_level()
        if state["task"] and not state["task"].done():
            state["task"].cancel()
        if s.recorder.recording:
            with suppress(Exception):
                s.recorder.stop()
