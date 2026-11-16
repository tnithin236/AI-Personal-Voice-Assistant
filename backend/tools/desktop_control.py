"""Allow-listed desktop automation. Nothing here ever runs a user-supplied command line."""
import difflib
import json
import logging
import re
import subprocess
import sys
import webbrowser
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path

from .base import ToolError

log = logging.getLogger(__name__)

# name -> executable (fixed strings; the model can only pick a key, never inject a command)
APP_ALLOWLIST = {
    "notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe",
    "file explorer": "explorer.exe", "explorer": "explorer.exe", "task manager": "taskmgr.exe",
    "command prompt": "cmd.exe", "powershell": "powershell.exe", "settings": "ms-settings:",
    "chrome": "chrome.exe", "google chrome": "chrome.exe", "edge": "msedge.exe", "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe", "vs code": "code", "vscode": "code", "visual studio code": "code",
    "word": "winword.exe", "excel": "excel.exe", "powerpoint": "powerpnt.exe", "spotify": "spotify.exe",
}
# User-added apps live in <project>/data/apps.json, e.g. {"copilot": "ms-copilot:"}.
# Values must look like an exe name, a path, or a URI scheme - no shell characters.
CUSTOM_APPS_FILE = Path(__file__).resolve().parents[2] / "data" / "apps.json"
_SAFE_TARGET = re.compile(r"^[\w\-. :\\/(){}!]+$")


def load_custom_apps(path: Path | None = None) -> dict[str, str]:
    path = path or CUSTOM_APPS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        log.warning("Ignoring unreadable %s: %s", path, e)
        return {}
    apps: dict[str, str] = {}
    for name, target in (data.items() if isinstance(data, dict) else []):
        if isinstance(name, str) and isinstance(target, str) and name.strip() and _SAFE_TARGET.match(target.strip()):
            target = target.strip()
            if "!" in target and not target.lower().startswith("shell:"):
                target = "shell:AppsFolder\\" + target  # a Windows app ID (from Get-StartApps) -> launchable address
            apps[name.strip().lower()] = target
        else:
            log.warning("Ignoring invalid or unsafe entry in apps.json: %r", name)
    return apps


def all_apps() -> dict[str, str]:
    return {**APP_ALLOWLIST, **load_custom_apps()}


KEY_ALLOWLIST = {"volume up": "volumeup", "volume down": "volumedown", "mute": "volumemute",
                 "play pause": "playpause", "next track": "nexttrack", "previous track": "prevtrack"}


def resolve_app(name: str, apps: dict[str, str]) -> tuple[str | None, list[str]]:
    """Match a spoken app name to a key of `apps`. Returns (key, suggestions); key is None unless exactly one
    app fits, so an ambiguous request is never guessed."""
    q = re.sub(r"\s+", " ", (name or "").strip().lower())
    q = re.sub(r"^(the|my)\s+", "", q)
    q = re.sub(r"\s+(app|application|program)$", "", q)
    if not q:
        return None, []
    if q in apps:
        return q, []
    if len(q) >= 3:
        starts = [k for k in apps if k.startswith(q)]
        words = [k for k in apps if re.search(rf"\b{re.escape(q)}\b", k)]
        if len(starts) == 1:
            return starts[0], []
        if not starts and len(words) == 1:
            return words[0], []
        pool = starts or words
        if len(pool) > 1:
            base = min(pool, key=len)
            if all(k.startswith(base) for k in pool):  # "vlc media player" + "...skinned": the base app is meant
                return base, []
            return None, sorted(pool, key=len)[:5]
    close = difflib.get_close_matches(q, list(apps), n=3, cutoff=0.85)
    if len(close) == 1:
        return close[0], []
    return None, close or difflib.get_close_matches(q, list(apps), n=3, cutoff=0.6)


def open_app(name: str) -> str:
    apps = all_apps()
    key, suggestions = resolve_app(name, apps)
    if key is None:
        hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        raise ToolError(f"'{name}' is not on my allowed apps list.{hint} You can add it in data/apps.json.")
    exe = apps[key]
    if sys.platform != "win32":
        raise ToolError("Opening apps is only implemented for Windows.")
    # `start` resolves App Paths (chrome, winword, ...) and URI schemes (ms-settings:)
    subprocess.Popen(["cmd", "/c", "start", "", exe], creationflags=subprocess.CREATE_NO_WINDOW)
    return f"Opening {key}."


def open_website(url: str) -> str:
    u = (url or "").strip()
    if not u:
        raise ToolError("Which website?")
    if "://" not in u:
        u = "https://" + u
    parsed = urlparse(u)
    host = parsed.hostname or ""
    if (parsed.scheme not in ("http", "https") or " " in u
            or not re.fullmatch(r"[\w.-]+", host) or not ("." in host or host == "localhost")):
        raise ToolError("That doesn't look like a valid web address (only http/https sites are allowed).")
    webbrowser.open(u)
    return f"Opened {u} in your browser."


def press_key(key: str) -> str:
    k = KEY_ALLOWLIST.get((key or "").strip().lower())
    if not k:
        raise ToolError(f"Allowed keys: {', '.join(KEY_ALLOWLIST)}.")
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.press(k)
    return f"Pressed {key}."


def take_screenshot(out_dir: Path | None = None) -> str:
    import pyautogui
    out = Path(out_dir or Path.home() / "Pictures")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"vaani_screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
    pyautogui.screenshot(str(path))
    return f"Saved screenshot to {path}"
