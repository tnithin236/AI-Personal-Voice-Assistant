"""Lets tests import modules that need httpx even when it is not installed (sandbox / CI)."""
import sys
import types

try:
    import httpx  # noqa: F401
except ImportError:
    sys.modules["httpx"] = types.ModuleType("httpx")
