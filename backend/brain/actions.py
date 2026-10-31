"""Pending confirmations for sensitive tool calls. Nothing runs until the user approves."""
import time
import uuid
from dataclasses import dataclass, field

TTL_SECONDS = 600


@dataclass
class PendingAction:
    tool: str
    args: dict
    conversation_id: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created: float = field(default_factory=time.time)


class PendingActions:
    def __init__(self):
        self._items: dict[str, PendingAction] = {}

    def create(self, tool: str, args: dict, conversation_id: str) -> PendingAction:
        self._purge()
        a = PendingAction(tool, args, conversation_id)
        self._items[a.id] = a
        return a

    def pop(self, action_id: str) -> PendingAction | None:
        self._purge()
        return self._items.pop(action_id, None)

    def _purge(self) -> None:
        now = time.time()
        for k in [k for k, v in self._items.items() if now - v.created > TTL_SECONDS]:
            del self._items[k]
