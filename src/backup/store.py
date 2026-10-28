"""JSON backup store: records original values before a change. Atomic writes; refuses to proceed on failure."""
import json, os, tempfile, time
from typing import Any, List

class BackupError(Exception): pass

class BackupStore:
    def __init__(self, directory: str):
        self.path = os.path.join(directory, "backups.json")
        os.makedirs(directory, exist_ok=True)

    def _load(self) -> List[dict]:
        if not os.path.exists(self.path): return []
        try:
            with open(self.path, encoding="utf-8") as f: data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise BackupError(f"Backup file unreadable: {e}")
        if not isinstance(data, list): raise BackupError("Backup file malformed")
        return data

    def record(self, change_id: str, original: Any) -> None:
        data = self._load()
        data.append({"id": change_id, "original": original, "time": time.time(), "restored": False})
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
            os.replace(tmp, self.path)
        except OSError as e:
            raise BackupError(f"Could not write backup: {e}")

    def pending(self) -> List[dict]:
        return [b for b in self._load() if not b["restored"]]

    def mark_restored(self, change_id: str) -> None:
        data = self._load()
        for b in reversed(data):
            if b["id"] == change_id and not b["restored"]:
                b["restored"] = True; break
        else:
            raise BackupError("No pending backup with that id")
        with open(self.path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
