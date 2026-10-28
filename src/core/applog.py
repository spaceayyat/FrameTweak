"""Local-only logging (named applog to avoid shadowing stdlib `logging`)."""
import logging, os
from logging.handlers import RotatingFileHandler

def data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.local/share")
    path = os.path.join(base, "FrameTweak")
    os.makedirs(path, exist_ok=True)
    return path

def get_logger() -> logging.Logger:
    log = logging.getLogger("frametweak")
    if not log.handlers:
        log.setLevel(logging.INFO)
        h = RotatingFileHandler(os.path.join(data_dir(), "frametweak.log"), maxBytes=512_000, backupCount=2, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
    return log

def log_path() -> str:
    return os.path.join(data_dir(), "frametweak.log")
