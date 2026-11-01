"""Central change engine: read -> backup -> write -> re-read to validate -> rollback on failure."""
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple
from src.backup.store import BackupStore, BackupError

@dataclass
class Tweak:
    id: str; name: str; what: str; why: str; drawbacks: str
    needs_admin: bool; reversible: bool
    read: Callable[[], Any]; write: Callable[[Any], None]
    target: Any  # the wanted value, or a function orig -> wanted value (used to change one flag and keep the rest)
    supported: Callable[[], bool] = lambda: True
    category: str = "General"
    note: str = ""  # extra caveat shown after a change, e.g. "Sign out and back in for it to take effect."

@dataclass
class Result:
    ok: bool; message: str

def resolve_target(t: Tweak, orig: Any) -> Any:
    """The value the tweak wants, given the value read just now."""
    return t.target(orig) if callable(t.target) else t.target

def is_applied(t: Tweak) -> Optional[bool]:
    """True/False when the setting can be read here, None when it cannot be determined."""
    try:
        if not t.supported(): return None
        cur = t.read()
        return cur == resolve_target(t, cur)
    except Exception:
        return None

def _short_key(key: str) -> str:
    """'Control Panel\\Mouse|MouseSpeed' -> 'Mouse\\MouseSpeed' (last key segment and value name)."""
    return key.rsplit("\\", 1)[-1].replace("|", "\\")

def format_value(v: Any) -> str:
    """Human-readable form of a stored value (multi-value tweaks keep a dict keyed 'path|name')."""
    if v is None: return "not set"
    if isinstance(v, dict): return ", ".join(f"{_short_key(str(k))}={format_value(x)}" for k, x in v.items())
    return repr(v)

def apply(t: Tweak, store: BackupStore) -> Result:
    if not t.supported():
        return Result(False, "Unavailable here (unsupported system, or administrator rights needed). Nothing changed.")
    try: orig = t.read()
    except Exception as e: return Result(False, f"Could not read the current setting. Nothing changed. ({e})")
    try: target = resolve_target(t, orig)
    except Exception as e: return Result(False, f"Could not work out the new value from the current setting. Nothing changed. ({e})")
    if orig == target: return Result(True, "Already set. Nothing to change.")
    try: store.record(t.id, {"value": orig})
    except BackupError as e: return Result(False, f"Backup failed, so nothing was changed. ({e})")
    try:
        t.write(target); now = t.read()
        if now == target: return Result(True, "Applied and verified." + (f" {t.note}" if t.note else ""))
        err = f"setting reads {now!r} after the change"
    except Exception as e:
        err = str(e)
    try:  # roll back to the original value
        t.write(orig)
        if t.read() == orig:
            store.mark_restored(t.id); return Result(False, f"Change failed ({err}). Original value restored.")
    except Exception as e2:
        err += f"; rollback also failed ({e2})"
    return Result(False, f"Change failed ({err}). Original value may not be restored; undo from the Tweaks page.")

def undo(t: Tweak, store: BackupStore) -> Result:
    try: pend = [b for b in store.pending() if b["id"] == t.id]
    except BackupError as e: return Result(False, f"Backups unreadable: {e}")
    if not pend: return Result(False, "No saved original value to restore.")
    orig = pend[-1]["original"]["value"]
    try:
        t.write(orig)
        if t.read() != orig: return Result(False, "Restore could not be verified.")
        store.mark_restored(t.id)
    except Exception as e:
        return Result(False, f"Restore failed: {e}")
    return Result(True, "Original value restored and verified.")

def undo_all(tweaks: List[Tweak], store: BackupStore) -> List[Tuple[str, Result]]:
    """Restore every tweak that still has a saved original. One entry per tweak, newest change first.

    If a tweak was applied more than once, every saved record is undone so the oldest original wins."""
    try: ids = [b["id"] for b in store.pending()]
    except BackupError as e: return [("Backups", Result(False, f"Backups unreadable: {e}"))]
    out = []
    for t in tweaks:
        n = ids.count(t.id)
        if not n: continue
        r = Result(False, "No saved original value to restore.")
        for _ in range(n):
            r = undo(t, store)
            if not r.ok: break
        out.append((t.name, r))
    return out
