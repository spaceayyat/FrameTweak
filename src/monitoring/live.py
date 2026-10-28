import psutil
from collections import deque
from typing import Optional

class LiveMonitor:
    """Samples real CPU/RAM/disk metrics. Unsupported metrics yield None."""
    def __init__(self, history: int = 60):
        self.cpu = deque(maxlen=history); self.ram = deque(maxlen=history); self.disk = deque(maxlen=history)
        self._last_io = psutil.disk_io_counters(); psutil.cpu_percent(None)

    def sample(self):
        self.cpu.append(psutil.cpu_percent(None))
        self.ram.append(psutil.virtual_memory().percent)
        io = psutil.disk_io_counters()
        if io and self._last_io:
            self.disk.append((io.read_bytes + io.write_bytes - self._last_io.read_bytes - self._last_io.write_bytes) / 1_048_576)
        self._last_io = io

    @staticmethod
    def top_processes(n: int = 8):
        rows = []
        for p in psutil.process_iter(["name", "memory_info"]):
            try: rows.append((p.info["name"] or "?", p.info["memory_info"].rss))
            except (psutil.Error, AttributeError): continue
        return sorted(rows, key=lambda r: r[1], reverse=True)[:n]

    @staticmethod
    def temperatures() -> Optional[dict]:
        f = getattr(psutil, "sensors_temperatures", None)
        try: return f() if f else None
        except Exception: return None
