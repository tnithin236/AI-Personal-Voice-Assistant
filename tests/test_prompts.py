import unittest

from backend.brain.prompts import LANG_RULES, system_prompt


class TamilPromptTests(unittest.TestCase):
    def test_tamil_rules_forbid_transliteration(self):
        for mode in ("ta", "auto"):
            self.assertIn("transliteration", LANG_RULES[mode])
        self.assertIn("Tamil script only", LANG_RULES["ta"])

    def test_rule_reaches_the_system_prompt(self):
        self.assertIn("transliteration", system_prompt("Vaani", "ta", "now"))
        self.assertIn("transliteration", system_prompt("Vaani", "auto", "now"))


if __name__ == "__main__":
    unittest.main()
