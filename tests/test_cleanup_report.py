import os, time
from src.cleanup import cleaner
from src.core import report, sysinfo
from src.tweaks.engine import Tweak

def _old(p, hours=48): t = time.time() - hours * 3600; os.utime(p, (t, t))

# ---- cleanup categories
def _tree(tmp_path, *rel):
    local, temp = tmp_path / "Local", tmp_path / "Temp"; temp.mkdir()
    for r in rel: (local / r).mkdir(parents=True)
    return local, temp

def test_only_existing_fixed_locations_are_offered(tmp_path):
    local, temp = _tree(tmp_path, "CrashDumps", "D3DSCache", os.path.join("NVIDIA", "DXCache"), os.path.join("Microsoft", "Windows", "WER"))
    cats = {c.id: c for c in cleaner.categories(str(local), str(temp))}
    assert set(cats) == {"user_temp", "crash_dumps", "wer_reports", "dx_shader_cache", "nv_dx_cache"}  # GLCache and AMD folders don't exist here
    for cid, c in cats.items():
        if cid != "user_temp": assert os.path.realpath(c.path).startswith(os.path.realpath(str(local)) + os.sep)

def test_shader_caches_start_unselected_with_an_explanation(tmp_path):
    local, temp = _tree(tmp_path, "CrashDumps", "D3DSCache", os.path.join("AMD", "DxCache"))
    cats = {c.id: c for c in cleaner.categories(str(local), str(temp))}
    assert cats["user_temp"].default_selected and cats["crash_dumps"].default_selected
    for cid in ("dx_shader_cache", "amd_dx_cache"):
        assert not cats[cid].default_selected and "recompile" in cats[cid].note and "rebuilds" in cats[cid].name

def test_no_localappdata_means_only_user_temp(tmp_path):
    temp = tmp_path / "Temp"; temp.mkdir()
    assert [c.id for c in cleaner.categories("", str(temp))] == ["user_temp"]

def test_shader_cache_cleaning_keeps_the_same_safety_rules(tmp_path):
    local, temp = _tree(tmp_path, "D3DSCache"); root = local / "D3DSCache"
    old, new = root / "old.bin", root / "new.bin"; old.write_bytes(b"x" * 10); new.write_bytes(b"y" * 10); _old(old)
    allowed = [c.path for c in cleaner.categories(str(local), str(temp))]
    r = cleaner.clean(str(root), allowed); assert r.bytes_removed == 10 and not old.exists() and new.exists() and root.exists()

# ---- report
def _snap(**kw):
    s = sysinfo.SystemSnapshot()
    for k, v in kw.items(): setattr(s, k, v)
    return s

def test_report_never_invents_values():
    text = report.build_report(sysinfo.SystemSnapshot(), [], [], now=0)
    assert "Game Mode:   Unavailable" in text and "RAM:         Unavailable" in text and "None available" in text and "None recorded yet" in text
    assert "No FPS is measured" in text and text.endswith("\n")

def test_report_shows_what_was_read():
    s = _snap(windows="Windows 11 (build 22631, AMD64)", supported=True, cpu="Test CPU", cpu_cores=16, gpu="Test GPU", ram_total=16 << 30,
              ram_available=8 << 30, disk_total=500 << 30, disk_free=100 << 30, power_plan="High performance", game_mode=True, notes=["a note"])
    text = report.build_report(s, [("Tweak A", "Applied"), ("Tweak B", "Not applied")], ["tweak apply a -> True: ok"], now=0)
    for part in ("Windows 11 (build 22631, AMD64)", "Test CPU (16 threads)", "Test GPU", "8.0 GB free of 16.0 GB", "100.0 GB free of 500.0 GB", "High performance",
                 "Game Mode:   On", "Tweak A: Applied", "Tweak B: Not applied", "tweak apply a -> True: ok", "a note"):
        assert part in text, part
    assert "unsupported" not in text

def test_report_flags_unsupported_windows():
    assert "(unsupported version)" in report.build_report(_snap(windows="Windows 7", supported=False), [], [], now=0)

def test_tweak_status_reads_each_setting():
    st = {"on": 1, "off": 0}
    mk = lambda i: Tweak(i, i.title(), "", "", "", False, True, lambda: st[i], lambda v: None, 1)
    off = mk("off"); off.supported = lambda: False
    broken = Tweak("x", "X", "", "", "", False, True, lambda: 1 / 0, lambda v: None, 1)
    assert report.tweak_status([mk("on"), mk("off"), off, broken]) == [("On", "Applied"), ("Off", "Not applied"), ("Off", "Unavailable"), ("X", "Unavailable")]

def test_save_report_never_overwrites_an_existing_file(tmp_path):
    p1 = report.save_report("first", str(tmp_path)); p2 = report.save_report("second", str(tmp_path))
    assert p1 != p2 and open(p1, encoding="utf-8").read() == "first" and open(p2, encoding="utf-8").read() == "second"
    assert os.path.basename(p1).startswith("FrameTweak-report-") and p1.endswith(".txt")

def test_save_report_creates_the_folder(tmp_path):
    p = report.save_report("x", str(tmp_path / "new" / "dir")); assert os.path.exists(p)
