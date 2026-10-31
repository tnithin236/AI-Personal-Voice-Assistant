"""RAM / CPU / VRAM snapshot used by /api/system and the benchmark scripts."""
import os


def snapshot() -> dict:
    out: dict = {}
    try:
        import psutil
        vm = psutil.virtual_memory()
        out["ram_used_mb"] = round((vm.total - vm.available) / 2**20)
        out["ram_total_mb"] = round(vm.total / 2**20)
        out["cpu_percent"] = psutil.cpu_percent(interval=None)
        out["backend_rss_mb"] = round(psutil.Process(os.getpid()).memory_info().rss / 2**20)
    except Exception as e:  # noqa: BLE001
        out["ram_error"] = str(e)
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        out["vram_used_mb"] = round(mem.used / 2**20)
        out["vram_total_mb"] = round(mem.total / 2**20)
        name = pynvml.nvmlDeviceGetName(h)
        out["gpu_name"] = name.decode() if isinstance(name, bytes) else name
        pynvml.nvmlShutdown()
    except Exception as e:  # noqa: BLE001
        out["gpu_error"] = str(e)
    return out
