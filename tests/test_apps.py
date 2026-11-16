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

    def test_windows_app_id_is_turned_into_a_launch_address(self):
        self.write({"copilot": "Microsoft.Copilot_8wekyb3d8bbwe!App",
                    "already": "shell:AppsFolder\\X.Y_abc!App"})
        apps = dc.load_custom_apps(self.file)
        self.assertEqual(apps["copilot"], "shell:AppsFolder\\Microsoft.Copilot_8wekyb3d8bbwe!App")
        self.assertEqual(apps["already"], "shell:AppsFolder\\X.Y_abc!App")

    def test_file_with_utf8_bom_is_accepted(self):
        self.file.write_bytes(b"\xef\xbb\xbf" + json.dumps({"copilot": "ms-copilot:"}).encode())
        self.assertEqual(dc.load_custom_apps(self.file), {"copilot": "ms-copilot:"})

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


APPS = {"docker desktop": "x1", "power bi desktop": "x2", "camera": "x3", "sticky notes": "x4", "notepad": "x5",
        "microsoft edge": "x6", "edge": "x7", "microsoft store": "x8", "microsoft teams": "x9", "claude": "x10",
        "visual studio code": "x11", "whatsapp": "x12", "mongodb compass": "x13"}


class ResolveAppTests(unittest.TestCase):
    def key(self, name):
        return dc.resolve_app(name, APPS)[0]

    def test_exact_and_normalised(self):
        self.assertEqual(self.key("camera"), "camera")
        self.assertEqual(self.key("  The Camera app "), "camera")
        self.assertEqual(self.key("my notepad"), "notepad")

    def test_unique_prefix_and_word_match(self):
        self.assertEqual(self.key("docker"), "docker desktop")
        self.assertEqual(self.key("power bi"), "power bi desktop")
        self.assertEqual(self.key("sticky note"), "sticky notes")
        self.assertEqual(self.key("compass"), "mongodb compass")        # whole-word match inside the name
        self.assertEqual(self.key("visual studio"), "visual studio code")

    def test_exact_beats_longer_names(self):
        self.assertEqual(self.key("edge"), "edge")                      # also "microsoft edge" exists

    def test_ambiguous_is_never_guessed(self):
        key, sugg = dc.resolve_app("microsoft", APPS)
        self.assertIsNone(key)
        self.assertTrue({"microsoft edge", "microsoft store", "microsoft teams"} <= set(sugg))

    def test_base_app_wins_when_the_others_are_variants_of_it(self):
        apps = {**APPS, "sticky notes (new)": "y1", "windows powershell": "y2", "windows powershell (x86)": "y3",
                "windows powershell ise": "y4", "python 3.12 (64-bit)": "y5", "python 3.13 (64-bit)": "y6"}
        self.assertEqual(dc.resolve_app("sticky note", apps)[0], "sticky notes")
        self.assertEqual(dc.resolve_app("windows power", apps)[0], "windows powershell")
        key, sugg = dc.resolve_app("python", apps)                      # two real alternatives: still refused
        self.assertIsNone(key)
        self.assertEqual(set(sugg), {"python 3.12 (64-bit)", "python 3.13 (64-bit)"})

    def test_short_fragments_do_not_prefix_match(self):
        self.assertIsNone(self.key("no"))
        self.assertIsNone(self.key("ca"))
        self.assertEqual(dc.resolve_app("", APPS), (None, []))

    def test_typo_accepted_only_when_clearly_one_app(self):
        self.assertEqual(self.key("whatsap"), "whatsapp")
        self.assertEqual(self.key("clude"), "claude")
        key, sugg = dc.resolve_app("photoshop", APPS)
        self.assertIsNone(key)

    def test_unknown_gives_suggestions_not_a_launch(self):
        with mock.patch.object(dc, "all_apps", return_value=APPS), \
             mock.patch.object(subprocess, "Popen") as popen:
            with self.assertRaises(ToolError) as cm:
                dc.open_app("microsoft")
        self.assertIn("Did you mean", str(cm.exception))
        popen.assert_not_called()

    def test_open_app_reports_the_app_it_really_opened(self):
        with mock.patch.object(dc, "all_apps", return_value=APPS), \
             mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(subprocess, "CREATE_NO_WINDOW", 0, create=True), \
             mock.patch.object(subprocess, "Popen") as popen:
            self.assertEqual(dc.open_app("docker"), "Opening docker desktop.")
        self.assertEqual(popen.call_args.args[0], ["cmd", "/c", "start", "", "x1"])


class GeneratedEntriesTests(unittest.TestCase):
    """Values like the ones scripts/import_start_apps.ps1 writes must pass Vaani's safety filter."""

    def test_typical_start_menu_addresses_are_accepted_and_bad_ones_rejected(self):
        d = Path(tempfile.mkdtemp()) / "apps.json"
        good = {"camera": "shell:AppsFolder\\Microsoft.WindowsCamera_8wekyb3d8bbwe!App",
                "sticky notes": "shell:AppsFolder\\Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe!App",
                "docker desktop": "shell:AppsFolder\\{6D809377-6AF0-444B-8957-A3773F02200E}\\Docker\\Docker\\Docker Desktop.exe",
                "chrome": "shell:AppsFolder\\Chrome",
                "pgadmin 4": "shell:AppsFolder\\C:\\Program Files\\PostgreSQL\\18\\pgAdmin 4\\runtime\\pgAdmin4.exe"}
        bad = {"x & y": "shell:AppsFolder\\a&b", "pipe": "shell:AppsFolder\\a|b", "quote": 'shell:AppsFolder\\a"b',
               "percent": "shell:AppsFolder\\%COMSPEC%"}
        d.write_text(json.dumps({**good, **bad}), encoding="utf-8")
        loaded = dc.load_custom_apps(d)
        self.assertEqual(set(loaded), set(good))
        self.assertEqual(loaded["camera"], good["camera"])             # already prefixed: left untouched


if __name__ == "__main__":
    unittest.main()
