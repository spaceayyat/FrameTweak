"""Central change engine: read -> backup -> write -> re-read to validate -> rollback on failure."""
from dataclasses import dataclass
from typing import Any, Callable
from src.backup.store import BackupStore, BackupError

@dataclass
class Tweak:
    id: str; name: str; what: str; why: str; drawbacks: str
    needs_admin: bool; reversible: bool
    read: Callable[[], Any]; write: Callable[[Any], None]; target: Any
    supported: Callable[[], bool] = lambda: True

@dataclass
class Result:
    ok: bool; message: str

def apply(t: Tweak, store: BackupStore) -> Result:
    if not t.supported():
        return Result(False, "Unavailable here (unsupported system, or administrator rights needed). Nothing changed.")
    try: orig = t.read()
    except Exception as e: return Result(False, f"Could not read the current setting. Nothing changed. ({e})")
    if orig == t.target: return Result(True, "Already set. Nothing to change.")
    try: store.record(t.id, {"value": orig})
    except BackupError as e: return Result(False, f"Backup failed, so nothing was changed. ({e})")
    try:
        t.write(t.target); now = t.read()
        if now == t.target: return Result(True, "Applied and verified.")
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
