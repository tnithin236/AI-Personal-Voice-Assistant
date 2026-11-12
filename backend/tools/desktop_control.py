"""Allow-listed desktop automation. Nothing here ever runs a user-supplied command line."""
import logging
import json
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


def open_app(name: str) -> str:
    key = (name or "").strip().lower()
    apps = all_apps()
    exe = apps.get(key)
    if not exe:
        raise ToolError(f"'{name}' is not on my allowed apps list. Allowed: {', '.join(sorted(apps))}. "
                        "New apps can be added in data/apps.json.")
    if sys.platform != "win32":
        raise ToolError("Opening apps is only implemented for Windows.")
    # `start` resolves App Paths (chrome, winword, ...) and URI schemes (ms-settings:)
    subprocess.Popen(["cmd", "/c", "start", "", exe], creationflags=subprocess.CREATE_NO_WINDOW)
    return f"Opening {name}."


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