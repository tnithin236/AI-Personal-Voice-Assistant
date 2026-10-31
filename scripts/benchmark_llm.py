"""Phase 1: benchmark gemma3:4b on this machine via Ollama.
   python scripts\\benchmark_llm.py [--num-ctx 4096] [--num-gpu N] [--model gemma3:4b]"""
import argparse
import subprocess
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
OLLAMA = "http://localhost:11434"
PROMPTS = {
    "English": "Explain in three sentences why the sky is blue.",
    "Tamil": "தமிழில் ஒரு சிறிய வாழ்த்து சொல்லுங்கள், பிறகு இரண்டு வாக்கியங்களில் உங்களை அறிமுகப்படுத்துங்கள்.",
}


def gpu_used() -> str:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                         capture_output=True, text=True)
    return out.stdout.strip()


def run(model, prompt, num_ctx, num_gpu):
    options = {"num_ctx": num_ctx, "temperature": 0.3, "num_predict": 200}
    if num_gpu is not None:
        options["num_gpu"] = num_gpu
    r = httpx.post(f"{OLLAMA}/api/generate", timeout=600,
                   json={"model": model, "prompt": prompt, "stream": False, "options": options, "keep_alive": "5m"})
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma3:4b")
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--num-gpu", type=int, default=None, help="GPU layers (omit = auto)")
    a = ap.parse_args()
    print(f"Model: {a.model} | num_ctx={a.num_ctx} | num_gpu={a.num_gpu if a.num_gpu is not None else 'auto'}")
    print(f"GPU before: {gpu_used()}\n")
    for name, prompt in PROMPTS.items():
        d = run(a.model, prompt, a.num_ctx, a.num_gpu)
        gen = d["eval_count"] / (d["eval_duration"] / 1e9)
        pp = d["prompt_eval_count"] / max(d["prompt_eval_duration"] / 1e9, 1e-9)
        print(f"--- {name} ---\nload {d['load_duration']/1e9:.2f}s | prompt {pp:.1f} tok/s | "
              f"generation {gen:.1f} tok/s | total {d['total_duration']/1e9:.2f}s")
        print(d["response"].strip(), "\n")
    for m in httpx.get(f"{OLLAMA}/api/ps").json().get("models", []):
        total, vram = m["size"], m["size_vram"]
        print(f"Loaded: {m['name']} | total {total/2**30:.2f} GiB | on GPU {vram/2**30:.2f} GiB "
              f"({100*vram/total:.0f}%) | on CPU {(total-vram)/2**30:.2f} GiB")
    print(f"GPU after: {gpu_used()}")


if __name__ == "__main__":
    main()
