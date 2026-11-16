"""Samples RAM / VRAM / CPU while you use the assistant. Start the backend, then:
       python scripts\\resource_report.py --seconds 90 --interval 2
   and during those seconds: ask a question, hold the mic, upload a document, etc.
   Also reports the memory used by Ollama, the backend and the Tamil voice service."""
import argparse
import sys
import time

BASE = "http://127.0.0.1:8000/api"


def classify(proc_info) -> str | None:
    name = (proc_info.get("name") or "").lower()
    cmd = " ".join(proc_info.get("cmdline") or []).lower()
    if "ollama" in name or "llama-server" in name:
        return "ollama (LLM)"
    if "backend.main" in cmd or "uvicorn" in cmd and "backend" in cmd:
        return "vaani backend"
    if "tamil_tts" in cmd:
        return "tamil voice service"
    if name.startswith("node"):
        return "frontend dev server"
    return None


def process_memory() -> dict[str, int]:
    import psutil
    totals: dict[str, int] = {}
    for p in psutil.process_iter(["name", "cmdline", "memory_info"]):
        try:
            kind = classify(p.info)
            if kind and p.info["memory_info"]:
                totals[kind] = totals.get(kind, 0) + p.info["memory_info"].rss // 2**20
        except Exception:  # noqa: BLE001 - processes can vanish mid-scan
            continue
    return totals


def summarize(samples: list[dict]) -> list[str]:
    def span(key):
        xs = [s[key] for s in samples if s.get(key) is not None]
        return (min(xs), max(xs)) if xs else None
    lines = []
    for label, key, unit in [("System RAM used", "ram_used_mb", "MB"), ("GPU memory used", "vram_used_mb", "MB"),
                             ("CPU", "cpu_percent", "%")]:
        sp = span(key)
        lines.append(f"{label:22s} min {sp[0]:>7} / peak {sp[1]:>7} {unit}" if sp else f"{label:22s} unavailable")
    kinds = sorted({k for s in samples for k in s.get("procs", {})})
    for k in kinds:
        peak = max(s.get("procs", {}).get(k, 0) for s in samples)
        lines.append(f"  {k:20s} peak {peak:>7} MB")
    total = samples[-1].get("ram_total_mb")
    vt = samples[-1].get("vram_total_mb")
    if total:
        lines.append(f"(machine: {total} MB RAM" + (f", {vt} MB VRAM)" if vt else ")"))
    return lines


def main():
    import httpx
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--interval", type=float, default=2.0)
    a = ap.parse_args()
    samples = []
    print(f"Sampling for {a.seconds}s - use the assistant now.\n")
    end = time.time() + a.seconds
    with httpx.Client(timeout=5) as c:
        while time.time() < end:
            try:
                s = c.get(f"{BASE}/system").json()
            except Exception as e:  # noqa: BLE001
                sys.exit(f"Backend not reachable: {e}")
            s["procs"] = process_memory()
            samples.append(s)
            print(f"RAM {s.get('ram_used_mb')} MB | VRAM {s.get('vram_used_mb', '-')} MB | CPU {s.get('cpu_percent')}%")
            time.sleep(a.interval)
    print("\n" + "\n".join(summarize(samples)))
    loaded = samples[-1].get("ollama_loaded") or []
    for m in loaded:
        pct = 100 * m["vram_mb"] / m["size_mb"] if m["size_mb"] else 0
        print(f"Ollama model {m['name']}: {m['vram_mb']} MB on GPU of {m['size_mb']} MB ({pct:.0f}% on GPU)")


if __name__ == "__main__":
    main()
