"""Local file search / folder creation / deletion, confined to the user's home folder."""
import os
import time
from pathlib import Path

from .base import ToolError

SKIP_DIRS = {"appdata", "node_modules", ".git", ".venv", "__pycache__", "$recycle.bin", "windows",
             "program files", "program files (x86)", "onedrivetemp"}
PROTECTED_NAMES = {"desktop", "documents", "downloads", "pictures", "music", "videos"}


def allowed_roots() -> list[Path]:
    return [Path.home().resolve()]


def safe_path(raw: str, base: Path | None = None) -> Path:
    """Resolve a user-supplied path; it must stay inside an allowed root."""
    if not raw or not raw.strip():
        raise ToolError("No path given.")
    p = Path(os.path.expandvars(os.path.expanduser(raw.strip().strip('"'))))
    if not p.is_absolute():
        p = (base or Path.home() / "Desktop") / p
    p = p.resolve()
    for root in allowed_roots():
        if p == root or root in p.parents:
            return p
    raise ToolError("For safety I only work inside your user folder.")


def search_files(query: str, limit: int = 15, max_seconds: float = 8.0) -> str:
    q = (query or "").strip().lower()
    if len(q) < 2:
        raise ToolError("Give me at least two characters of the file name.")
    start, hits, scanned = time.time(), [], 0
    for root in allowed_roots():
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for name in filenames + dirnames:
                scanned += 1
                if q in name.lower():
                    hits.append(str(Path(dirpath) / name))
                    if len(hits) >= limit:
                        return "\n".join(hits)
            if time.time() - start > max_seconds or scanned > 400_000:
                break
    return "\n".join(hits) if hits else f"No files matching '{query}' were found in your user folder."


def create_folder(path: str) -> str:
    p = safe_path(path)
    if p.exists():
        return f"The folder already exists: {p}"
    p.mkdir(parents=True, exist_ok=True)
    return f"Created folder: {p}"


def delete_path(path: str) -> str:
    p = safe_path(path)
    if p in allowed_roots() or p.name.lower() in PROTECTED_NAMES and p.parent == Path.home().resolve():
        raise ToolError("I won't delete a top-level user folder.")
    if not p.exists():
        raise ToolError(f"Not found: {p}")
    if p.is_file():
        p.unlink()
        return f"Deleted file: {p}"
    if p.is_dir():
        try:
            p.rmdir()
        except OSError:
            raise ToolError("That folder is not empty. I only delete empty folders; delete it manually if you're sure.")
        return f"Deleted empty folder: {p}"
    raise ToolError("Unsupported path type.")
