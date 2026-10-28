import os, time, pytest
from src.tweaks.engine import Tweak, apply, undo
from src.backup.store import BackupStore
from src.cleanup import cleaner

def make(state, fail_write=False, ignore_write=False):
    def w(v):
        if fail_write: raise OSError("denied")
        if not ignore_write: state["v"] = v
    return Tweak("t", "T", "", "", "", False, True, lambda: state.get("v"), w, 1)

def test_apply_and_undo(tmp_path):
    s = {}; st = BackupStore(str(tmp_path)); t = make(s)
    assert apply(t, st).ok and s["v"] == 1
    assert undo(t, st).ok and s["v"] is None and st.pending() == []

def test_apply_restores_original_value(tmp_path):
    s = {"v": 0}; st = BackupStore(str(tmp_path)); t = make(s)
    apply(t, st); assert s["v"] == 1; undo(t, st); assert s["v"] == 0

def test_write_failure_changes_nothing(tmp_path):
    s = {"v": 0}; r = apply(make(s, fail_write=True), BackupStore(str(tmp_path)))
    assert not r.ok and s["v"] == 0

def test_validation_failure_reported(tmp_path):
    s = {"v": 0}; r = apply(make(s, ignore_write=True), BackupStore(str(tmp_path)))
    assert not r.ok and "restored" in r.message.lower()

def test_backup_failure_aborts(tmp_path):
    (tmp_path / "backups.json").write_text("garbage"); s = {"v": 0}
    r = apply(make(s), BackupStore(str(tmp_path))); assert not r.ok and s["v"] == 0

def test_unsupported_and_noop(tmp_path):
    s = {}; t = make(s); t.supported = lambda: False
    assert not apply(t, BackupStore(str(tmp_path))).ok and s == {}
    s2 = {"v": 1}; assert apply(make(s2), BackupStore(str(tmp_path))).message.startswith("Already")

def test_undo_without_backup(tmp_path):
    assert not undo(make({}), BackupStore(str(tmp_path))).ok

def test_power_guid_validation():
    from src.tweaks.catalog import power_write
    with pytest.raises(ValueError): power_write("x; calc.exe")

def _old(p, hours=48): t = time.time() - hours * 3600; os.utime(p, (t, t))

def test_cleanup_removes_only_old_files(tmp_path):
    root = tmp_path / "tmp"; (root / "sub").mkdir(parents=True)
    old = root / "sub" / "old.bin"; old.write_bytes(b"x" * 100); _old(old)
    new = root / "new.bin"; new.write_bytes(b"y" * 50)
    assert cleaner.analyze(str(root), [str(root)]) == (100, 1)
    r = cleaner.clean(str(root), [str(root)])
    assert r.bytes_removed == 100 and not old.exists() and new.exists() and not (root / "sub").exists() and root.exists()

def test_cleanup_rejects_bad_roots(tmp_path):
    d = tmp_path / "Downloads"; d.mkdir()
    with pytest.raises(ValueError): cleaner.clean(str(d), [str(d)])
    with pytest.raises(ValueError): cleaner.clean(str(tmp_path), [str(d)])
    with pytest.raises(ValueError): cleaner.validate_root("/", ["/"])

def test_cleanup_does_not_follow_symlinks(tmp_path):
    outside = tmp_path / "outside"; outside.mkdir(); f = outside / "keep.txt"; f.write_text("k"); _old(f)
    root = tmp_path / "tmp"; root.mkdir()
    try: os.symlink(outside, root / "link", target_is_directory=True)
    except OSError: pytest.skip("symlinks unavailable")
    cleaner.clean(str(root), [str(root)]); assert f.exists()

def test_locked_file_skipped(tmp_path, monkeypatch):
    root = tmp_path / "tmp"; root.mkdir(); f = root / "a"; f.write_text("a"); _old(f)
    monkeypatch.setattr(os, "remove", lambda p: (_ for _ in ()).throw(PermissionError(13, "locked")))
    r = cleaner.clean(str(root), [str(root)]); assert r.skipped == 1 and r.bytes_removed == 0
