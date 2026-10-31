import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services import get_services

router = APIRouter(prefix="/api", tags=["chat"])


class ChatIn(BaseModel):
    text: str
    conversation_id: str | None = None


class RegenIn(BaseModel):
    conversation_id: str


class RenameIn(BaseModel):
    title: str


async def _collect(coro_fn) -> list[dict]:
    events: list[dict] = []

    async def emit(e: dict):
        events.append(e)

    await coro_fn(emit)
    return events


def _result(events: list[dict]) -> dict:
    err = next((e for e in events if e["type"] == "error"), None)
    if err:
        raise HTTPException(503, err["message"])
    done = next(e for e in reversed(events) if e["type"] == "done")
    pending = next((e for e in events if e["type"] == "pending_action"), None)
    return {"conversation_id": done["conversation_id"], "reply": done["text"], "language": done["language"],
            "tool": done["tool"], "timings": done["timings"], "pending_action": pending}


@router.post("/chat")
async def chat(body: ChatIn):
    s = get_services()
    if not body.text.strip():
        raise HTTPException(400, "Empty message")
    cid, _ = s.ensure_conversation(body.conversation_id)
    events = await _collect(lambda emit: s.agent.respond(cid, body.text.strip(), emit))
    return _result(events)


@router.post("/chat/regenerate")
async def regenerate(body: RegenIn):
    s = get_services()
    text = s.convo.last_user_text(body.conversation_id)
    if text is None:
        raise HTTPException(404, "Nothing to regenerate")
    s.convo.delete_last_assistant(body.conversation_id)
    events = await _collect(lambda emit: s.agent.respond(body.conversation_id, text, emit, save_user=False))
    return _result(events)


@router.get("/conversations")
def list_conversations():
    return get_services().convo.list()


@router.post("/conversations")
def create_conversation():
    return {"id": get_services().convo.create()}


@router.get("/conversations/{cid}")
def get_conversation(cid: str):
    conv = get_services().convo.get(cid)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.patch("/conversations/{cid}")
def rename_conversation(cid: str, body: RenameIn):
    get_services().convo.rename(cid, body.title)
    return {"ok": True}


@router.post("/conversations/{cid}/clear")
def clear_conversation(cid: str):
    get_services().convo.clear(cid)
    return {"ok": True}


@router.delete("/conversations/{cid}")
def delete_conversation(cid: str):
    get_services().convo.delete(cid)
    return {"ok": True}
