import json
from src.startup.inspect_startup import StartupEntry
from src.startup.manage import make_tweak, ENABLED, DISABLED
from src.tweaks import engine
from src.backup.store import BackupStore
from src.debloat import appx

def fake_io():
    d = {}; return d, (lambda h, k, n: d.get((h, k, n)), lambda h, k, n, v: d.pop((h, k, n), None) if v is None else d.__setitem__((h, k, n), v))

E = StartupEntry("Foo", "HKCU Run", "foo.exe", "Enabled", "HKCU", "Run", "Foo")

def test_startup_disable_enable_undo(tmp_path):
    d, io = fake_io(); st = BackupStore(str(tmp_path))
    assert engine.apply(make_tweak(E, False, io), st).ok and list(d.values()) == [DISABLED]
    assert engine.undo(make_tweak(E, True, io), st).ok and d == {}          # originally unset -> deleted again
    d[("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run", "Foo")] = ENABLED
    assert engine.apply(make_tweak(E, False, io), st).ok and engine.undo(make_tweak(E, True, io), st).ok and list(d.values()) == [ENABLED]

def test_startup_admin_flag():
    assert make_tweak(StartupEntry("x", "HKLM Run", "", "Enabled", "HKLM", "Run", "x"), False).needs_admin
    assert not make_tweak(E, False).needs_admin

RAW = json.dumps([
 {"Name": "Microsoft.BingWeather", "PackageFullName": "Microsoft.BingWeather_4.5_x64__8wekyb3d8bbwe", "Publisher": "CN=Microsoft Corporation, O=X", "IsFramework": False, "NonRemovable": False},
 {"Name": "Microsoft.SecHealthUI", "PackageFullName": "Microsoft.SecHealthUI_1_x64__8w", "Publisher": "CN=Microsoft", "IsFramework": False, "NonRemovable": False},
 {"Name": "Microsoft.WindowsStore", "PackageFullName": "Microsoft.WindowsStore_1_x64__8w", "Publisher": "CN=M", "IsFramework": False, "NonRemovable": False},
 {"Name": "Microsoft.VCLibs.140", "PackageFullName": "Microsoft.VCLibs.140_1", "IsFramework": True},
 {"Name": "Microsoft.GetHelp", "PackageFullName": "Microsoft.GetHelp_1", "IsFramework": False, "NonRemovable": True}])

def test_parse_and_classify():
    assert appx.parse_packages("") == [] and appx.parse_packages("garbage") == []
    assert len(appx.parse_packages(json.dumps({"Name": "a", "PackageFullName": "b"}))) == 1
    apps = {a.name: a for a in appx.classify(appx.parse_packages(RAW))}
    assert apps["Microsoft.BingWeather"].removable and apps["Microsoft.BingWeather"].publisher == "Microsoft Corporation"
    assert not apps["Microsoft.SecHealthUI"].removable and not apps["Microsoft.WindowsStore"].removable
    assert "Microsoft.VCLibs.140" not in apps and not apps["Microsoft.GetHelp"].removable

def test_curated_list_never_contains_protected():
    assert not [n for n in appx.CURATED if appx.DENY.search(n)]

def _app(n="Microsoft.BingWeather"): return next(a for a in appx.classify(appx.parse_packages(RAW)) if a.name == n)

def test_remove_verified_and_failures():
    a = _app()
    assert appx.remove(a, scan_fn=lambda: [], runner=lambda f: None).ok
    assert "still installed" in appx.remove(a, scan_fn=lambda: [a], runner=lambda f: None).message
    assert "failed" in appx.remove(a, scan_fn=lambda: [], runner=lambda f: "denied").message

def test_remove_refuses_ineligible():
    called = []
    for n in ("Microsoft.SecHealthUI", "Microsoft.WindowsStore", "Microsoft.GetHelp"):
        assert not appx.remove(_app(n), runner=lambda f: called.append(f)).ok
    bad = _app(); bad.full_name = "x'; calc #"
    assert not appx.remove(bad, runner=lambda f: called.append(f)).ok and called == []
