"""Allow-listed desktop automation. Nothing here ever runs a user-supplied command line."""
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
KEY_ALLOWLIST = {"volume up": "volumeup", "volume down": "volumedown", "mute": "volumemute",
                 "play pause": "playpause", "next track": "nexttrack", "previous track": "prevtrack"}


def open_app(name: str) -> str:
    key = (name or "").strip().lower()
    exe = APP_ALLOWLIST.get(key)
    if not exe:
        raise ToolError(f"'{name}' is not on my allowed apps list. Allowed: {', '.join(sorted(APP_ALLOWLIST))}.")
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
