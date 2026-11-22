"""Latency report from the backend log (data/logs/vaani.log).
   Use the assistant for a while (voice + text, English + Tamil), then run:
       python scripts\\log_report.py                      # the latest backend session only
       python scripts\\log_report.py --all                # every session in the log
       python scripts\\log_report.py --since "2026-11-13 10:00"   # only newer entries
"""
import argparse
import ast
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RE_STT = re.compile(r"STT (\d+)ms lang=(\w+) \(([\d.]+)\)")
RE_REPLY = re.compile(r"Reply done: (\{.*\})")
RE_TTS = re.compile(r"TTS ([\w\-]+) (\d+)ms (\d+) chars")
RE_DIRECT = re.compile(r"Direct tool reply \((\w+)\)")


def percentile(values, p):
    s = sorted(values)
    return s[max(0, math.ceil(p / 100 * len(s)) - 1)]


SESSION_MARK = "Vaani starting"


def latest_session(lines):
    """Lines after the most recent 'Vaani starting' marker (older sessions include crashes and first-load runs)."""
    for i in range(len(lines) - 1, -1, -1):
        if SESSION_MARK in lines[i]:
            return lines[i:]
    return lines


def parse(lines, since=None):
    d = {"stt_all": [], "stt_en": [], "stt_ta": [], "retrieval_ms": [], "tool_ms": [], "first_token_ms": [],
         "total_ms": [], "tokens_per_s": [], "tts": {}, "direct_replies": 0}
    for line in lines:
        if since and line[:19] < since:
            continue
        if m := RE_STT.search(line):
            ms, lang = int(m.group(1)), m.group(2)
            d["stt_all"].append(ms)
            d.setdefault(f"stt_{lang}", []).append(ms)
        elif m := RE_REPLY.search(line):
            try:
                t = ast.literal_eval(m.group(1))
            except (ValueError, SyntaxError):
                continue
            for k in ("retrieval_ms", "tool_ms", "first_token_ms", "total_ms", "tokens_per_s"):
                if t.get(k) is not None:
                    d[k].append(t[k])
        elif m := RE_TTS.search(line):
            d["tts"].setdefault(m.group(1), []).append(int(m.group(2)))
        elif RE_DIRECT.search(line):
            d["direct_replies"] += 1
    return d


def row(name, xs, unit="ms"):
    if not xs:
        return f"{name:34s} {'-':>5s}"
    return (f"{name:34s} {len(xs):5d} {statistics.median(xs):10.0f} {percentile(xs, 95):10.0f} "
            f"{max(xs):10.0f}  {unit}")


def report_markdown(d) -> str:
    """Same numbers as report(), as a Markdown table you can paste into the README or TESTING.md."""
    rows = [("Speech recognition, all", d["stt_all"], "ms"), ("Speech recognition, English", d.get("stt_en", []), "ms"),
            ("Speech recognition, Tamil", d.get("stt_ta", []), "ms"),
            ("Memory / document retrieval", d["retrieval_ms"], "ms"), ("Tool step (router + tool)", d["tool_ms"], "ms"),
            ("Time to first word (text)", d["first_token_ms"], "ms"), ("Reply complete (text)", d["total_ms"], "ms"),
            ("Generation speed", d["tokens_per_s"], "tok/s")]
    rows += [(f"Speech synthesis: {m}", xs, "ms") for m, xs in sorted(d["tts"].items())]
    out = ["| Metric | n | Median | p95 | Max |", "|---|---:|---:|---:|---:|"]
    for name, xs, unit in rows:
        if xs:
            out.append(f"| {name} ({unit}) | {len(xs)} | {statistics.median(xs):.0f} | {percentile(xs, 95):.0f} | {max(xs):.0f} |")
    return "\n".join(out)


def report(d) -> str:
    out = [f"{'metric':34s} {'n':>5s} {'median':>10s} {'p95':>10s} {'max':>10s}", "-" * 78]
    out += [row("speech recognition (all)", d["stt_all"]),
            row("  English", d.get("stt_en", [])), row("  Tamil", d.get("stt_ta", [])),
            row("memory/document retrieval", d["retrieval_ms"]),
            row("tool step (router + tool)", d["tool_ms"]),
            row("time to first word (text)", d["first_token_ms"]),
            row("reply total (text done)", d["total_ms"]),
            row("generation speed", d["tokens_per_s"], "tok/s")]
    for mode, xs in sorted(d["tts"].items()):
        out.append(row(f"speech synthesis: {mode}", xs))
    out.append(f"\ndirect action replies (no LLM): {d['direct_replies']}")
    if d["stt_en"] and d["first_token_ms"] and d["tts"]:
        tts = statistics.median([x for v in d["tts"].values() for x in v])
        est = (statistics.median(d["stt_en"]) + statistics.median(d["retrieval_ms"] or [0])
               + statistics.median(d["first_token_ms"]) + tts)
        out.append(f"\nRough time from releasing the mic to the first spoken word (English, sum of medians):"
                   f" {est / 1000:.1f} s\n  + about 1 s while Gemma finishes the first sentence (at ~20 tok/s)."
                   "\n  (STT includes one-off model loads, which can push the first numbers up.)")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / "data" / "logs" / "vaani.log"))
    ap.add_argument("--markdown", action="store_true", help="print a Markdown table instead of plain text")
    ap.add_argument("--all", action="store_true", help="include every session, not just the latest")
    ap.add_argument("--since", help='e.g. "2026-11-13 10:00" (compared with the log timestamps)')
    a = ap.parse_args()
    path = Path(a.file)
    if not path.exists():
        sys.exit(f"Log not found: {path} (start the backend and use the assistant first)")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not a.all and not a.since:
        lines = latest_session(lines)
    d = parse(lines, a.since)
    print(report_markdown(d) if a.markdown else report(d))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
