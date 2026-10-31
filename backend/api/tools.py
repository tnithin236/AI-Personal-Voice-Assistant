import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services import get_services
from backend.tools.base import ToolError
from backend.tools.registry import REGISTRY, describe_action

router = APIRouter(prefix="/api", tags=["tools"])


class RunIn(BaseModel):
    tool: str
    args: dict = {}


class ConfirmIn(BaseModel):
    approve: bool


@router.get("/tools")
def list_tools():
    return [{"name": t.name, "description": t.description, "params": t.params,
             "sensitive": t.sensitive, "automation": t.automation} for t in REGISTRY.values()]


@router.post("/tools/run")
async def run_tool(body: RunIn):
    s = get_services()
    spec = REGISTRY.get(body.tool)
    if not spec:
        raise HTTPException(404, "Unknown tool")
    args = {k: str(body.args.get(k, "")).strip() for k in spec.params}
    if any(not v for v in args.values()):
        raise HTTPException(400, f"Missing argument(s): {', '.join(k for k, v in args.items() if not v)}")
    if spec.sensitive or (s.settings.get("confirm_all_actions") and spec.automation):
        pending = s.actions.create(body.tool, args, "")
        return {"pending_action": {"id": pending.id, "tool": body.tool,
                                   "description": describe_action(body.tool, args)}}
    try:
        return {"result": await asyncio.to_thread(spec.fn, **args)}
    except ToolError as e:
        raise HTTPException(400, str(e))


@router.post("/actions/{action_id}/confirm")
async def confirm_action(action_id: str, body: ConfirmIn):
    try:
        return await get_services().agent.run_confirmed(action_id, body.approve)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
