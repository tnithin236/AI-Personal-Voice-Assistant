from dataclasses import dataclass, field
from typing import Callable


class ToolError(Exception):
    """Raised by a tool for expected, user-presentable failures."""


@dataclass
class ToolSpec:
    name: str
    description: str
    fn: Callable[..., str]
    params: dict[str, str] = field(default_factory=dict)  # arg name -> description (all required)
    sensitive: bool = False     # always needs user confirmation
    automation: bool = False    # needs confirmation when "confirm all actions" is on
    direct_reply: bool = False  # answer with the tool's own text (no LLM): actions must never be misreported
    describe: Callable[[dict], str] | None = None  # human text for confirmation prompts
