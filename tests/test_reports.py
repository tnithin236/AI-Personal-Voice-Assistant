import unittest

from scripts import log_report, resource_report

LOG = """\
2026-11-05 17:36:08,320 | INFO    | backend.brain.agent | Memories used: [(0.222, 'The user works as a data analyst.')]
2026-11-05 17:36:11,996 | INFO    | backend.brain.agent | Reply done: {'retrieval_ms': 114, 'tool_ms': 2282, 'first_token_ms': 988, 'total_ms': 3789, 'tokens_per_s': 22.4}
2026-11-05 17:36:12,115 | INFO    | backend.voice.text_to_speech | TTS piper-in-process 113ms 30 chars
2026-11-05 18:00:00,000 | INFO    | backend.voice.speech_to_text | STT 2479ms lang=en (1.00): What is the capital of France?
2026-11-05 18:00:03,000 | INFO    | backend.brain.agent | Reply done: {'retrieval_ms': 16, 'tool_ms': 0, 'first_token_ms': 1456, 'total_ms': 1906, 'tokens_per_s': 20.5}
2026-11-05 18:00:04,000 | INFO    | backend.voice.text_to_speech | TTS piper-in-process 127ms 59 chars
2026-11-05 18:05:00,000 | INFO    | backend.voice.speech_to_text | STT 4641ms lang=ta (0.98): உன்னுடைய பெயர் என்ன?
2026-11-05 18:05:03,000 | INFO    | backend.brain.agent | Reply done: {'retrieval_ms': 20, 'tool_ms': 0, 'first_token_ms': None, 'total_ms': 50, 'tokens_per_s': None}
2026-11-05 18:05:04,000 | INFO    | backend.voice.text_to_speech | TTS tamil-service 450ms 40 chars
2026-11-05 18:06:00,000 | INFO    | backend.brain.agent | Direct tool reply (open_app): Opening copilot.
something unrelated
"""


class LogReportTests(unittest.TestCase):
    def test_parse_everything(self):
        d = log_report.parse(LOG.splitlines())
        self.assertEqual(d["stt_all"], [2479, 4641])
        self.assertEqual((d["stt_en"], d["stt_ta"]), ([2479], [4641]))
        self.assertEqual(d["first_token_ms"], [988, 1456])            # None skipped
        self.assertEqual(d["tts"], {"piper-in-process": [113, 127], "tamil-service": [450]})
        self.assertEqual(d["direct_replies"], 1)

    def test_since_filters_old_entries(self):
        d = log_report.parse(LOG.splitlines(), since="2026-11-05 18:00")
        self.assertEqual(d["stt_all"], [2479, 4641])
        self.assertEqual(d["total_ms"], [1906, 50])

    def test_percentile_and_report_render(self):
        self.assertEqual(log_report.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95), 10)
        self.assertEqual(log_report.percentile([5], 50), 5)
        text = log_report.report(log_report.parse(LOG.splitlines()))
        self.assertIn("speech recognition", text)
        self.assertIn("Rough time from releasing the mic", text)

    def test_latest_session_only(self):
        lines = ["2026-11-01 10:00:00,000 | INFO | vaani | Vaani starting | model=x",
                 "2026-11-01 10:00:05,000 | INFO | b | Reply done: {'retrieval_ms': 7413, 'tool_ms': 0, 'first_token_ms': 25000, 'total_ms': 29000, 'tokens_per_s': 5.0}",
                 "2026-11-13 20:14:24,288 | INFO | vaani | Vaani starting | model=gemma3:4b",
                 "2026-11-13 20:16:17,159 | INFO | b | Reply done: {'retrieval_ms': 20, 'tool_ms': 0, 'first_token_ms': 1154, 'total_ms': 1830, 'tokens_per_s': 19.9}"]
        d = log_report.parse(log_report.latest_session(lines))
        self.assertEqual(d["first_token_ms"], [1154])
        self.assertEqual(len(log_report.parse(lines)["first_token_ms"]), 2)         # --all keeps both
        self.assertEqual(log_report.latest_session(["no marker here"]), ["no marker here"])

    def test_stt_line_with_beam_still_parses(self):
        d = log_report.parse(["2026-11-13 20:00:00,000 | INFO | s | STT 1500ms lang=en (1.00) beam=1: hello"])
        self.assertEqual(d["stt_en"], [1500])

    def test_empty_log_does_not_crash(self):
        self.assertIn("metric", log_report.report(log_report.parse([])))


class ResourceReportTests(unittest.TestCase):
    def test_classify_processes(self):
        c = resource_report.classify
        self.assertEqual(c({"name": "ollama.exe", "cmdline": []}), "ollama (LLM)")
        self.assertEqual(c({"name": "llama-server.exe", "cmdline": []}), "ollama (LLM)")
        self.assertEqual(c({"name": "python.exe", "cmdline": ["python", "-m", "uvicorn", "backend.main:app"]}), "vaani backend")
        self.assertEqual(c({"name": "python.exe", "cmdline": ["python", "services/tamil_tts/server.py"]}), "tamil voice service")
        self.assertIsNone(c({"name": "chrome.exe", "cmdline": []}))

    def test_summarize(self):
        samples = [{"ram_used_mb": 9000, "vram_used_mb": 3000, "cpu_percent": 10, "ram_total_mb": 24000,
                    "vram_total_mb": 4096, "procs": {"ollama (LLM)": 2800}},
                   {"ram_used_mb": 11000, "vram_used_mb": 3500, "cpu_percent": 80, "ram_total_mb": 24000,
                    "vram_total_mb": 4096, "procs": {"ollama (LLM)": 3100, "vaani backend": 1500}}]
        text = "\n".join(resource_report.summarize(samples))
        self.assertIn("peak   11000 MB", text)
        self.assertIn("ollama (LLM)", text)
        self.assertIn("3100", text)

    def test_summarize_without_gpu(self):
        text = "\n".join(resource_report.summarize([{"ram_used_mb": 1, "cpu_percent": 1, "ram_total_mb": 2, "procs": {}}]))
        self.assertIn("unavailable", text)


if __name__ == "__main__":
    unittest.main()
