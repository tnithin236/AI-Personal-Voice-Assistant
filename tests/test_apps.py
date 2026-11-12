import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.tools import desktop_control as dc
from backend.tools.base import ToolError


class CustomAppsTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.file = self.dir / "apps.json"

    def write(self, obj):
        self.file.write_text(json.dumps(obj), encoding="utf-8")

    def test_missing_file_is_fine(self):
        self.assertEqual(dc.load_custom_apps(self.file), {})

    def test_valid_entries_loaded_and_lowercased(self):
        self.write({"Copilot": "ms-copilot:", "My Editor": "C:\\Program Files\\Ed\\ed.exe", "whatsapp": "whatsapp:"})
        apps = dc.load_custom_apps(self.file)
        self.assertEqual(apps["copilot"], "ms-copilot:")
        self.assertIn("my editor", apps)
        self.assertEqual(len(apps), 3)

    def test_shell_characters_rejected(self):
        self.write({"bad1": "calc & del /q *", "bad2": "calc | more", "bad3": "x > y", "bad4": "a\nb",
                    "bad5": "%COMSPEC%", "bad6": "x^y", 'bad7': 'a"b', "ok": "calc.exe"})
        self.assertEqual(list(dc.load_custom_apps(self.file)), ["ok"])

    def test_corrupt_or_wrong_shape_ignored(self):
        self.file.write_text("{not json", encoding="utf-8")
        self.assertEqual(dc.load_custom_apps(self.file), {})
        self.write(["a", "b"])
        self.assertEqual(dc.load_custom_apps(self.file), {})
        self.write({"a": 5, "": "calc.exe"})
        self.assertEqual(dc.load_custom_apps(self.file), {})

    def test_builtin_apps_cannot_be_overridden_silently_but_custom_wins_when_user_asks(self):
        self.write({"notepad": "C:\\tools\\mynotepad.exe"})
        with mock.patch.object(dc, "CUSTOM_APPS_FILE", self.file):
            self.assertEqual(dc.all_apps()["notepad"], "C:\\tools\\mynotepad.exe")  # the user's own file wins

    def test_open_app_launches_custom_entry_without_a_shell_string(self):
        self.write({"copilot": "ms-copilot:"})
        with mock.patch.object(dc, "CUSTOM_APPS_FILE", self.file), \
             mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(subprocess, "CREATE_NO_WINDOW", 0, create=True), \
             mock.patch.object(subprocess, "Popen") as popen:
            self.assertIn("Opening", dc.open_app("Copilot"))
            popen.assert_called_once()
            self.assertEqual(popen.call_args.args[0], ["cmd", "/c", "start", "", "ms-copilot:"])

    def test_unknown_app_still_refused_and_error_mentions_apps_json(self):
        with mock.patch.object(dc, "CUSTOM_APPS_FILE", self.file):
            with self.assertRaises(ToolError) as cm:
                dc.open_app("format c:")
        self.assertIn("apps.json", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
