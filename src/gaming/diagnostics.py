"""Real, measured diagnostics. Nothing here measures FPS. Findings cite their evidence and avoid definitive bottleneck claims."""
import ctypes, datetime, sys, threading, time
import psutil
from src.core import sysinfo, winproc
from src.monitoring.live import LiveMonitor

CANCEL = threading.Event()
T_RAM, T_CPU, T_DISK, T_TEMP, T_GPU = 85.0, 85.0, 50.0, 85.0, 95.0

def gpu_info():
    """NVIDIA only (via nvidia-smi if present). AMD/Intel readings are Unavailable."""
    try:
        r = winproc.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"], timeout=5)
        if r.returncode != 0: return None
        n, u, t, mu, mt = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        return {"name": n, "util": int(u), "temp": int(t), "mem_used_mb": int(mu), "mem_total_mb": int(mt)}
    except Exception: return None

def temperatures():
    f = getattr(psutil, "sensors_temperatures", None)
    try: d = f() if f else None
    except Exception: return None
    out = {k: max(t.current for t in v) for k, v in (d or {}).items() if v}
    return out or None

def display_info():
    if sys.platform != "win32": return None
    try:
        from ctypes import wintypes as w
        class DM(ctypes.Structure):
            _fields_ = [("n", ctypes.c_wchar * 32), ("sv", w.WORD), ("dv", w.WORD), ("size", w.WORD), ("extra", w.WORD), ("fields", w.DWORD),
                        ("px", ctypes.c_long), ("py", ctypes.c_long), ("orient", w.DWORD), ("fixed", w.DWORD), ("color", ctypes.c_short),
                        ("duplex", ctypes.c_short), ("yres", ctypes.c_short), ("tt", ctypes.c_short), ("collate", ctypes.c_short),
                        ("form", ctypes.c_wchar * 32), ("logpix", w.WORD), ("bpp", w.DWORD), ("width", w.DWORD), ("height", w.DWORD),
                        ("flags", w.DWORD), ("hz", w.DWORD), ("icm", w.DWORD), ("intent", w.DWORD), ("media", w.DWORD), ("dither", w.DWORD),
                        ("r1", w.DWORD), ("r2", w.DWORD), ("panw", w.DWORD), ("panh", w.DWORD)]
        dm = DM(); dm.size = ctypes.sizeof(DM)
        if not ctypes.windll.user32.EnumDisplaySettingsW(None, ctypes.c_uint32(0xFFFFFFFF), ctypes.byref(dm)): return None
        return {"width": dm.width, "height": dm.height, "hz": dm.hz if dm.hz > 1 else None}
    except Exception: return None

_avg = lambda v: round(sum(v) / len(v), 1) if v else None
_max = lambda v: round(max(v), 1) if v else None

def collect(seconds=10, interval=1.0, sleep=time.sleep) -> dict:
    CANCEL.clear(); procs = []
    for p in psutil.process_iter(["name"]):
        try: p.cpu_percent(None); procs.append(p)
        except psutil.Error: pass
    psutil.cpu_percent(None); last = psutil.disk_io_counters(); cpu, ram, disk = [], [], []
    for _ in range(max(1, int(seconds / interval))):
        if CANCEL.is_set(): break
        sleep(interval); cpu.append(psutil.cpu_percent(None)); ram.append(psutil.virtual_memory().percent)
        io = psutil.disk_io_counters()
        if io and last: disk.append(((io.read_bytes + io.write_bytes) - (last.read_bytes + last.write_bytes)) / 1048576 / interval)
        last = io
    n = psutil.cpu_count() or 1; share = {}
    for p in procs:
        try: share[p.info.get("name") or "?"] = share.get(p.info.get("name") or "?", 0) + p.cpu_percent(None) / n
        except psutil.Error: pass
    return {"time": datetime.datetime.now().isoformat(timespec="seconds"), "seconds": len(cpu), "cpu_avg": _avg(cpu), "cpu_max": _max(cpu),
            "ram_avg": _avg(ram), "ram_max": _max(ram), "disk_avg": _avg(disk), "disk_max": _max(disk),
            "top_cpu": [(k, round(v, 1)) for k, v in sorted(share.items(), key=lambda x: -x[1])[:5]],
            "top_ram": [(k, v) for k, v in LiveMonitor.top_processes(5)], "gpu": gpu_info(), "temps": temperatures(), "display": display_info(),
            "game_mode": sysinfo.game_mode_enabled(), "power_plan": sysinfo.power_plan()}

def analyze(s: dict) -> list:
    f = []; add = lambda lvl, t, e, n: f.append({"level": lvl, "title": t, "evidence": e, "note": n})
    sec = s.get("seconds")
    if (s.get("ram_avg") or 0) >= T_RAM:
        add("watch", "Possible memory pressure", f"RAM averaged {s['ram_avg']}% (peak {s['ram_max']}%) over {sec} s.",
            "High usage alone isn't a fault (Windows caches). It matters if stutter happens while RAM is nearly full; closing large background apps may help.")
    if (s.get("cpu_avg") or 0) >= T_CPU:
        tops = ", ".join(f"{n} {v}%" for n, v in s.get("top_cpu", [])[:3])
        add("watch", "CPU heavily loaded", f"CPU averaged {s['cpu_avg']}% (peak {s['cpu_max']}%). Biggest contributors: {tops or 'unavailable'}.",
            "This is whole-PC load, not proof a game is CPU-limited. If no game was running, these are background processes you could close manually.")
    if (s.get("disk_avg") or 0) >= T_DISK:
        add("watch", "Sustained disk activity", f"Disk throughput averaged {s['disk_avg']} MB/s (peak {s['disk_max']}).",
            "Heavy background disk use can cause hitching, especially on hard drives. Check which apps are updating or syncing.")
    g = s.get("gpu")
    if g:
        if g["util"] >= T_GPU and (s.get("cpu_avg") is None or s["cpu_avg"] < 70):
            add("info", "GPU looks heavily used", f"GPU at {g['util']}% in a single reading while CPU averaged {s.get('cpu_avg')}%.",
                "Consistent with a GPU-limited workload at that moment (lower resolution or graphics settings would help), but one reading is not proof.")
        if g["temp"] >= T_TEMP: add("watch", "High GPU temperature", f"GPU reported {g['temp']} °C.", "Check case airflow and fan curves; sustained high temperatures can trigger throttling.")
    for k, v in (s.get("temps") or {}).items():
        if v >= T_TEMP: add("watch", f"High temperature on {k}", f"Sensor reported {v:.0f} °C.", "Sensor readings vary by hardware; verify with your motherboard/GPU vendor tool.")
    if not f:
        add("ok", "No resource pressure seen in this sample", f"CPU avg {s.get('cpu_avg')}%, RAM avg {s.get('ram_avg')}%, disk avg {s.get('disk_avg')} MB/s over {sec} s.",
            "This did not measure FPS. For bottleneck evidence, start the diagnostic and then return to your running game.")
    return f
