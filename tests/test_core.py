import json, pytest
from src.core import sysinfo
from src.startup.inspect_startup import parse_approved, read_startup_entries
from src.backup.store import BackupStore, BackupError
from src.monitoring.live import LiveMonitor

def test_fmt_bytes():
    assert sysinfo.fmt_bytes(None) == "Unavailable"
    assert sysinfo.fmt_bytes(2048) == "2.0 KB"

def test_collect_never_raises_and_marks_unavailable(monkeypatch):
    monkeypatch.setattr(sysinfo, "IS_WINDOWS", False)
    s = sysinfo.collect()
    assert s.windows is None and s.power_plan is None and s.game_mode is None
    assert s.notes and s.ram_total

def test_run_ps_non_windows(monkeypatch):
    monkeypatch.setattr(sysinfo, "IS_WINDOWS", False)
    assert sysinfo.run_ps("x") is None

def test_parse_approved():
    assert parse_approved(b"\x02\x00") == "Enabled"
    assert parse_approved(b"\x06\x00") == "Enabled"
    assert parse_approved(b"\x03\x00") == "Disabled"
    assert parse_approved(b"") == "Unknown"

def test_startup_non_windows():
    import sys
    if sys.platform != "win32": assert read_startup_entries() == []

def test_backup_roundtrip(tmp_path):
    b = BackupStore(str(tmp_path)); b.record("gamemode", {"AutoGameModeEnabled": 0})
    assert b.pending()[0]["original"] == {"AutoGameModeEnabled": 0}
    b.mark_restored("gamemode"); assert b.pending() == []
    with pytest.raises(BackupError): b.mark_restored("gamemode")

def test_backup_corrupt_aborts(tmp_path):
    (tmp_path / "backups.json").write_text("{not json")
    with pytest.raises(BackupError): BackupStore(str(tmp_path)).record("x", 1)

def test_monitor_samples():
    m = LiveMonitor(); m.sample(); m.sample()
    assert len(m.cpu) == 2 and len(m.ram) == 2
