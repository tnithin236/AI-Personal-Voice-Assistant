import os
import tempfile
import unittest
from pathlib import Path

from backend.brain import tool_router as tr
from backend.tools.base import ToolError
from backend.tools.calculator import calculate
from backend.tools.registry import REGISTRY, describe_action


class CalculatorTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(calculate("2+2").split("= ")[1], "4")
        self.assertEqual(calculate("2^10").split("= ")[1], "1024")
        self.assertEqual(calculate("3 x 4").split("= ")[1], "12")
        self.assertEqual(calculate("sqrt(144)").split("= ")[1], "12")
        self.assertEqual(calculate("0.15*200").split("= ")[1], "30")
        self.assertEqual(calculate("10/4").split("= ")[1], "2.5")

    def test_rejects_code(self):
        for bad in ["__import__('os').system('dir')", "open('x')", "().__class__", "a+1", "", "9**9**9", "1/0"]:
            with self.assertRaises(ToolError, msg=bad):
                calculate(bad)


class RouterTests(unittest.TestCase):
    def test_hints(self):
        self.assertTrue(tr.looks_like_tool_request("what's the time"))
        self.assertTrue(tr.looks_like_tool_request("open notepad"))
        self.assertTrue(tr.looks_like_tool_request("what is 12 * 7"))
        self.assertFalse(tr.looks_like_tool_request("tell me a joke"))

    def test_validate(self):
        c = tr.validate_call({"tool": "calculator", "args": {"expression": "2+2", "junk": 1}})
        self.assertEqual((c.tool, c.args), ("calculator", {"expression": "2+2"}))
        self.assertIsNone(tr.validate_call({"tool": "calculator", "args": {}}))
        self.assertIsNone(tr.validate_call({"tool": "format_disk", "args": {}}))
        self.assertIsNone(tr.validate_call({"tool": None, "args": {}}))
        self.assertIsNone(tr.validate_call({"tool": "open_app", "args": "notepad"}))
        self.assertEqual(tr.validate_call({"tool": "datetime", "args": None}).tool, "datetime")

    def test_prompt_lists_every_tool(self):
        p = tr.router_prompt()
        for name in REGISTRY:
            self.assertIn(name, p)

    def test_sensitive_flags(self):
        self.assertTrue(REGISTRY["delete_path"].sensitive)
        self.assertIn("DELETE", describe_action("delete_path", {"path": "C:/x"}))


class FileManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = os.environ.get("HOME")
        os.environ["HOME"] = self.tmp  # Path.home() follows $HOME on Linux
        os.environ["USERPROFILE"] = self.tmp
        (Path(self.tmp) / "Desktop").mkdir()
        from backend.tools import file_manager
        self.fm = file_manager

    def tearDown(self):
        os.environ["HOME"] = self.old or ""

    def test_confined_to_home(self):
        with self.assertRaises(ToolError):
            self.fm.safe_path("/etc/passwd")
        with self.assertRaises(ToolError):
            self.fm.safe_path("../../etc")
        self.assertTrue(str(self.fm.safe_path("notes")).startswith(self.tmp))

    def test_create_search_delete(self):
        self.fm.create_folder("my_projects")
        self.assertTrue((Path(self.tmp) / "Desktop" / "my_projects").is_dir())
        f = Path(self.tmp) / "Desktop" / "my_projects" / "report_final.txt"
        f.write_text("hi")
        self.assertIn("report_final.txt", self.fm.search_files("report_final"))
        with self.assertRaises(ToolError):
            self.fm.delete_path(str(f.parent))          # not empty
        self.fm.delete_path(str(f))
        self.assertFalse(f.exists())
        self.fm.delete_path(str(f.parent))
        with self.assertRaises(ToolError):
            self.fm.delete_path(str(Path(self.tmp) / "Desktop"))   # protected
        with self.assertRaises(ToolError):
            self.fm.delete_path(self.tmp)


class DesktopTests(unittest.TestCase):
    def test_allowlist(self):
        from backend.tools import desktop_control as dc
        with self.assertRaises(ToolError):
            dc.open_app("rm -rf /")
        with self.assertRaises(ToolError):
            dc.open_website("javascript:alert(1)")
        with self.assertRaises(ToolError):
            dc.press_key("alt+f4")


if __name__ == "__main__":
    unittest.main()
