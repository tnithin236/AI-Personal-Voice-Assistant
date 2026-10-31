"""Single source of truth for tools. The router (LLM) can only pick entries from here."""
from .base import ToolSpec
from .calculator import calculate
from .datetime_tool import current_datetime
from .desktop_control import open_app, open_website, press_key, take_screenshot
from .file_manager import create_folder, delete_path, search_files
from .web_search import web_search

REGISTRY: dict[str, ToolSpec] = {t.name: t for t in [
    ToolSpec("calculator", "Evaluate an arithmetic expression.", calculate,
             {"expression": "math expression using + - * / ** % and parentheses, e.g. 12.5*(3+4)"}),
    ToolSpec("datetime", "Get the current local date and time.", current_datetime, {}),
    ToolSpec("web_search", "Search the web for current information.", web_search,
             {"query": "short search query"}),
    ToolSpec("file_search", "Find files or folders by name inside the user's folder.", search_files,
             {"query": "part of the file name"}),
    ToolSpec("open_app", "Open an application (notepad, calculator, chrome, edge, vs code, ...).", open_app,
             {"name": "application name"}, automation=True, describe=lambda a: f"open the app '{a.get('name')}'"),
    ToolSpec("open_website", "Open a website in the default browser.", open_website,
             {"url": "web address, e.g. youtube.com"}, automation=True,
             describe=lambda a: f"open the website {a.get('url')}"),
    ToolSpec("create_folder", "Create a folder (relative paths go on the Desktop).", create_folder,
             {"path": "folder path or name"}, automation=True,
             describe=lambda a: f"create the folder {a.get('path')}"),
    ToolSpec("delete_path", "Delete a single file or an empty folder.", delete_path,
             {"path": "full path of the file or empty folder"}, sensitive=True,
             describe=lambda a: f"DELETE {a.get('path')}"),
    ToolSpec("press_key", "Press a media key: volume up, volume down, mute, play pause, next track.", press_key,
             {"key": "one of the allowed key names"}, automation=True,
             describe=lambda a: f"press '{a.get('key')}'"),
    ToolSpec("screenshot", "Take a screenshot and save it to Pictures.", take_screenshot, {}, automation=True,
             describe=lambda a: "take a screenshot"),
]}


def describe_action(tool: str, args: dict) -> str:
    spec = REGISTRY[tool]
    return spec.describe(args) if spec.describe else f"run {tool}"
