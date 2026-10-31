"""Phase 8: end-to-end latency of the running backend (text path), plus RAM/VRAM.
   Start the backend first, then:  python scripts\\benchmark_pipeline.py"""
import sys
import time

import httpx

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000/api"
PROMPTS = ["Hello! Who are you?", "What is the capital of France?", "What's the time?",
           "Calculate 15% of 2480", "வணக்கம், எப்படி இருக்கிறீர்கள்?"]


def main():
    c = httpx.Client(timeout=300)
    cid = None
    print(f"{'prompt':42s} {'wall s':>7s} {'retr ms':>8s} {'1st tok ms':>10s} {'tok/s':>6s}")
    for p in PROMPTS:
        t = time.perf_counter()
        r = c.post(f"{BASE}/chat", json={"text": p, "conversation_id": cid})
        wall = time.perf_counter() - t
        if r.status_code != 200:
            print(f"{p[:40]:42s} ERROR {r.status_code}: {r.text[:120]}")
            continue
        d = r.json()
        cid = d["conversation_id"]
        tm = d["timings"]
        print(f"{p[:40]:42s} {wall:7.1f} {tm['retrieval_ms']:8d} {str(tm['first_token_ms']):>10s} {str(tm['tokens_per_s']):>6s}")
        print(f"    -> {d['reply'][:110]!r}  tool={d['tool']}")
    print("\nSystem:", c.get(f"{BASE}/system").json())


if __name__ == "__main__":
    main()
