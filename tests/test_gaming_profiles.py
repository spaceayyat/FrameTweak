import json, pytest
from src.gaming import diagnostics as dg
from src.profiles.store import ProfileStore, validate_profile, compare_snapshots

def test_collect_real_but_fast(monkeypatch):
    s = dg.collect(seconds=2, interval=1.0, sleep=lambda x: None)
    assert s["seconds"] == 2 and s["ram_avg"] is not None and 0 <= s["cpu_avg"] <= 100 and s["display"] is None

def test_analyze_cites_evidence_and_hedges():
    f = dg.analyze({"seconds": 10, "ram_avg": 92.0, "ram_max": 95.0, "cpu_avg": 30.0, "cpu_max": 50.0, "disk_avg": 1.0, "disk_max": 2.0,
                    "gpu": {"util": 99, "temp": 70}, "top_cpu": []})
    t = {x["title"]: x for x in f}
    assert "92.0%" in t["Possible memory pressure"]["evidence"]
    assert "not proof" in t["GPU looks heavily used"]["note"] and "bottleneck" not in " ".join(x["title"] for x in f).lower()

def test_analyze_clean_and_unavailable():
    f = dg.analyze({"seconds": 5, "ram_avg": 40.0, "cpu_avg": 10.0, "disk_avg": None, "gpu": None, "temps": None})
    assert f[0]["level"] == "ok" and "did not measure FPS" in f[0]["note"]
    assert dg.analyze({})[0]["level"] == "ok"

def test_gpu_missing_is_none(monkeypatch):
    monkeypatch.setattr(dg.winproc, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    assert dg.gpu_info() is None

def test_profile_validation():
    ok = validate_profile({"name": " Apex ", "exe": "r5apex.exe", "tweaks": ["game_mode", "game_mode"]}); assert ok["name"] == "Apex" and ok["tweaks"] == ["game_mode"]
    for bad in ({"name": ""}, {"name": "x", "tweaks": ["format_c"]}, {"name": "x", "exe": "..\\evil.bat"}, {"name": "x", "exe": "a/b.exe"}, [], {"name": "x", "notes": "n" * 501}, {"name": "a\nb"}):
        with pytest.raises(ValueError): validate_profile(bad)

def test_store_roundtrip_import_export(tmp_path):
    s = ProfileStore(str(tmp_path)); s.save({"name": "Mine", "tweaks": ["power_high"]})
    assert [p["name"] for p in s.all()][:3] == ["Balanced", "Gaming", "Low Background Activity"] and s.custom()[0]["name"] == "Mine"
    f = tmp_path / "e.json"; s.export("Mine", str(f)); s.delete("Mine"); assert s.custom() == []
    assert s.import_file(str(f))["tweaks"] == ["power_high"]
    with pytest.raises(ValueError): s.save({"name": "Gaming"})

def test_import_rejects_bad_files(tmp_path):
    s = ProfileStore(str(tmp_path)); p = tmp_path / "x.json"
    for body in ('{"name":"x"}', "[1]", "__import__('os').system('calc')", json.dumps({"frametweak_profile": 1, "name": "x", "tweaks": ["nope"]})):
        p.write_text(body)
        with pytest.raises(ValueError): s.import_file(str(p))   # JSONDecodeError is a ValueError
    p.write_text(" " * 200_000)
    with pytest.raises(ValueError): s.import_file(str(p))

def test_history_and_compare(tmp_path):
    s = ProfileStore(str(tmp_path)); a = {"time": "t1", "cpu_avg": 40.0, "ram_avg": 70.0, "disk_avg": None, "game_mode": False}; b = {"time": "t2", "cpu_avg": 30.0, "ram_avg": 65.5, "disk_avg": 2.0, "game_mode": True}
    s.add_history(a); s.add_history(b); assert len(s.history()) == 2
    r = {x[0]: x for x in compare_snapshots(a, b)}
    assert r["CPU average"][3] == "-10.0%" and r["Disk activity average"][3] == "n/a" and r["Game Mode"][1:3] == ("Off", "On")
    s.delete_history(["t1"]); assert [x["time"] for x in s.history()] == ["t2"]
