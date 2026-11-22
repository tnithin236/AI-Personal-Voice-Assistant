"""Guards against the launcher bug where an unquoted script path broke on folders containing spaces."""
import re
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


class LauncherQuotingTests(unittest.TestCase):
    def setUp(self):
        self.text = (SCRIPTS / "start_all.ps1").read_text(encoding="utf-8")

    def test_script_path_is_quoted_when_opening_windows(self):
        self.assertIn('-File `"$PSScriptRoot\\$script`""', self.text)

    def test_no_unquoted_file_argument_in_any_script(self):
        for ps1 in SCRIPTS.glob("*.ps1"):
            for n, line in enumerate(ps1.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                self.assertIsNone(re.search(r'"-File",\s*"\$PSScriptRoot', line), f"{ps1.name}:{n} unquoted path: {line}")

    def test_all_three_services_use_the_helper(self):
        for name in ("start_backend.ps1", "start_tamil_tts.ps1", "start_frontend.ps1"):
            self.assertIn(f'Start-Window "{name}"', self.text)
            self.assertTrue((SCRIPTS / name).exists())

    def test_every_script_changes_to_the_project_root_itself(self):
        for name in ("start_backend.ps1", "start_frontend.ps1", "start_tamil_tts.ps1"):
            self.assertIn("Set-Location", (SCRIPTS / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
