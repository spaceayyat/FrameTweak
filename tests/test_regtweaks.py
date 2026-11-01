import json, os, sys, pytest
from src.backup.store import BackupStore
from src.tweaks import engine
from src.tweaks.engine import Tweak, apply, undo, undo_all, is_applied, format_value
from src.tweaks.regtweaks import DWORD, SZ, RegValue, check_value, clear_flag_bit, flags_without_bit, registry_tweak

class FakeReg:
    """In-memory stand-in for HKCU. Records every write so tests can assert exactly what was touched."""
    def __init__(self, data=None): self.data, self.writes = dict(data or {}), []
    def read(self, path, name): return self.data.get((path, name))
    def write(self, path, name, kind, val):
        self.writes.append((path, name, kind, val))
        if val is None: self.data.pop((path, name), None)
        else: self.data[(path, name)] = val
    @property
    def io(self): return (self.read, self.write)

A, B = RegValue("K\\One", "A", DWORD, 0), RegValue("K\\Two", "B", SZ, "0")

def tweak(reg, **kw): return registry_tweak("t", "T", "what", "why", "drawbacks", [A, B], io=reg.io, **kw)

# ---- registry_tweak
def test_multi_value_apply_then_undo_restores_exact_originals(tmp_path):
    reg = FakeReg({("K\\One", "A"): 1}); st = BackupStore(str(tmp_path)); t = tweak(reg)  # B starts 'not set'
    r = apply(t, st); assert r.ok and r.message.startswith("Applied and verified"), r
    assert reg.data == {("K\\One", "A"): 0, ("K\\Two", "B"): "0"}
    assert undo(t, st).ok and reg.data == {("K\\One", "A"): 1}  # A back to 1, B deleted again (was not set)

def test_note_is_shown_after_apply(tmp_path):
    t = tweak(FakeReg(), note="Sign out."); assert apply(t, BackupStore(str(tmp_path))).message.endswith("Sign out.")

def test_already_set_changes_nothing(tmp_path):
    reg = FakeReg({("K\\One", "A"): 0, ("K\\Two", "B"): "0"}); r = apply(tweak(reg), BackupStore(str(tmp_path)))
    assert r.ok and r.message.startswith("Already") and reg.writes == []

def test_wrong_registry_type_is_refused_not_coerced(tmp_path):
    reg = FakeReg({("K\\Two", "B"): 5}); r = apply(tweak(reg), BackupStore(str(tmp_path)))  # B should be text, is a number
    assert not r.ok and "Nothing changed" in r.message and reg.writes == []

def test_failed_second_write_rolls_back_the_first(tmp_path):
    reg = FakeReg({("K\\One", "A"): 7}); orig_write = reg.write
    def flaky(path, name, kind, val):
        if path == "K\\Two" and val is not None: raise OSError("denied")
        orig_write(path, name, kind, val)
    t = registry_tweak("t", "T", "w", "y", "d", [A, B], io=(reg.read, flaky))
    r = apply(t, BackupStore(str(tmp_path))); assert not r.ok and "restored" in r.message.lower() and reg.data == {("K\\One", "A"): 7}

def test_restore_only_writes_declared_values_and_types():
    reg = FakeReg(); t = tweak(reg)
    t.write({"K\\One|A": 3, "K\\Two|B": "9", "HKEY\\Evil|x": 1, "K\\One|Extra": 1})  # extras from a tampered backup are ignored
    assert sorted((p, n) for p, n, *_ in reg.writes) == [("K\\One", "A"), ("K\\Two", "B")]

@pytest.mark.parametrize("bad", ["text", None, [], {"K\\One|A": 1}, {"K\\One|A": "1", "K\\Two|B": "0"}, {"K\\One|A": True, "K\\Two|B": "0"},
                                  {"K\\One|A": -1, "K\\Two|B": "0"}, {"K\\One|A": 2 ** 32, "K\\Two|B": "0"}, {"K\\One|A": 1, "K\\Two|B": 5}])
def test_restore_validates_everything_before_writing_anything(bad):
    reg = FakeReg(); t = tweak(reg)
    with pytest.raises(ValueError): t.write(bad)
    assert reg.writes == []

def test_registry_tweak_definition_errors():
    with pytest.raises(ValueError): registry_tweak("t", "T", "w", "y", "d", [], io=FakeReg().io)
    with pytest.raises(ValueError): registry_tweak("t", "T", "w", "y", "d", [RegValue("K", "A", DWORD)], io=FakeReg().io)  # no target
    with pytest.raises(ValueError): RegValue("K", "A", "binary", 1)
    with pytest.raises(ValueError): RegValue("K\\x", "a|b", DWORD, 1)
    with pytest.raises(ValueError): RegValue("", "a", DWORD, 1)
    with pytest.raises(ValueError): registry_tweak("t", "T", "w", "y", "d", [RegValue("K", "A", DWORD, True)], io=FakeReg().io)

def test_check_value_types():
    assert check_value(A, None) is None and check_value(A, 5) == 5 and check_value(B, "x") == "x"
    for rv, bad in ((A, "5"), (A, True), (A, 1.5), (B, 5), (B, b"x")):
        with pytest.raises(ValueError): check_value(rv, bad)

# ---- flag-bit tweaks
def test_clear_flag_bit_keeps_other_bits():
    assert clear_flag_bit("510", 4, 510) == "506" and clear_flag_bit("511", 4, 510) == "507" and clear_flag_bit("506", 4, 510) == "506"
    assert clear_flag_bit(None, 4, 126) == "122"  # not set -> Windows default, minus the hotkey bit
    with pytest.raises(ValueError): clear_flag_bit("not a number", 4, 510)

def sticky_tweak(reg):
    vals = [RegValue("Acc\\Sticky", "Flags", SZ), RegValue("Acc\\Filter", "Flags", SZ)]
    defaults = {vals[0].key: 510, vals[1].key: 126}
    return registry_tweak("s", "Sticky", "w", "y", "d", vals, target_fn=flags_without_bit(vals, defaults, 4), io=reg.io)

def test_sticky_flags_keep_user_settings_and_undo_exactly(tmp_path):
    reg = FakeReg({("Acc\\Sticky", "Flags"): "511"}); t = sticky_tweak(reg); st = BackupStore(str(tmp_path))
    assert is_applied(t) is False
    assert apply(t, st).ok and reg.data == {("Acc\\Sticky", "Flags"): "507", ("Acc\\Filter", "Flags"): "122"}
    assert is_applied(t) is True and apply(t, st).message.startswith("Already")
    assert undo(t, st).ok and reg.data == {("Acc\\Sticky", "Flags"): "511"}

def test_unparseable_flags_are_left_alone(tmp_path):
    reg = FakeReg({("Acc\\Sticky", "Flags"): "weird"}); r = apply(sticky_tweak(reg), BackupStore(str(tmp_path)))
    assert not r.ok and "Nothing changed" in r.message and reg.writes == []

# ---- engine helpers
def simple(state, tid="t", target=1):
    return Tweak(tid, tid.upper(), "", "", "", False, True, lambda: state.get(tid), lambda v: state.__setitem__(tid, v), target)

def test_callable_target_is_resolved_from_current_value(tmp_path):
    s = {"t": 10}; t = simple(s, target=lambda cur: cur + 5)
    assert apply(t, BackupStore(str(tmp_path))).ok and s["t"] == 15

def test_is_applied_states():
    s = {}; t = simple(s); assert is_applied(t) is False
    s["t"] = 1; assert is_applied(t) is True
    t.supported = lambda: False; assert is_applied(t) is None
    t2 = simple(s); t2.read = lambda: (_ for _ in ()).throw(OSError("x")); assert is_applied(t2) is None

def test_undo_all_restores_every_pending_tweak(tmp_path):
    s = {"a": 0, "b": None}; ta, tb, tc = simple(s, "a"), simple(s, "b"), simple(s, "c"); st = BackupStore(str(tmp_path))
    apply(ta, st); apply(tb, st)
    res = undo_all([ta, tb, tc], st)  # tc was never applied, so it is not listed
    assert [(n, r.ok) for n, r in res] == [("A", True), ("B", True)] and s == {"a": 0, "b": None} and st.pending() == []

def test_undo_all_goes_back_to_the_oldest_original_after_repeat_applies(tmp_path):
    s = {"a": 0}; t = simple(s, "a"); st = BackupStore(str(tmp_path))
    apply(t, st); s["a"] = 5  # something else changed it, then it is applied again
    apply(t, st); assert s["a"] == 1 and len(st.pending()) == 2
    res = undo_all([t], st); assert res[0][1].ok and s["a"] == 0 and st.pending() == []

def test_undo_all_with_unreadable_backups(tmp_path):
    (tmp_path / "backups.json").write_text("garbage"); res = undo_all([simple({})], BackupStore(str(tmp_path)))
    assert len(res) == 1 and not res[0][1].ok and "unreadable" in res[0][1].message

def test_format_value():
    assert format_value(None) == "not set" and format_value(1) == "1" and format_value("x") == "'x'"
    assert format_value({"Control Panel\\Mouse|MouseSpeed": "1", "K\\Game|Dvr": None}) == "Mouse\\MouseSpeed='1', Game\\Dvr=not set"

# ---- the real catalog
from src.tweaks.catalog import catalog, CATEGORIES, HOTKEY_BIT
from src.profiles.store import KNOWN, PRESETS, validate_profile

def test_catalog_entries_are_complete_and_safe():
    ts = catalog(); ids = [t.id for t in ts]
    assert len(ids) == len(set(ids)) and len(ts) >= 9
    for t in ts:
        assert all(isinstance(x, str) and x.strip() for x in (t.name, t.what, t.why, t.drawbacks)), t.id
        assert t.category in CATEGORIES and t.reversible and not t.needs_admin, t.id
        assert "fps" not in t.why.lower() and "guarantee" not in (t.why + t.drawbacks).lower(), t.id  # no promised gains

def test_building_the_catalog_never_touches_the_system():
    ts = catalog(); assert all(callable(t.read) and callable(t.write) for t in ts)  # only closures are built
    if sys.platform != "win32": assert not any(t.supported() for t in ts)

def test_catalog_only_touches_the_current_user_hive():
    root = os.path.dirname(os.path.dirname(__file__))
    for f in ("src/tweaks/catalog.py", "src/tweaks/regtweaks.py"):
        t = open(os.path.join(root, f), encoding="utf-8").read(); assert "HKEY_LOCAL_MACHINE" not in t and "HKLM" not in t, f

def test_profile_tweaks_exist_and_names_match_the_catalog():
    by_id = {t.id: t for t in catalog()}
    assert set(KNOWN) <= set(by_id) and all(KNOWN[i] == by_id[i].name for i in KNOWN)
    for name, p in PRESETS.items():
        d = validate_profile({"name": name, "tweaks": p["tweaks"], "notes": p["notes"]}); assert d["tweaks"] == p["tweaks"], name

def test_original_presets_unchanged_and_competitive_added():
    assert list(PRESETS)[:3] == ["Balanced", "Gaming", "Low Background Activity"] and "Competitive" in PRESETS
    assert PRESETS["Gaming"]["tweaks"] == ["game_mode", "power_high"]

def test_sticky_catalog_tweak_uses_windows_defaults_when_values_are_missing():
    import src.tweaks.catalog as c
    t = next(x for x in catalog() if x.id == "sticky_keys_prompts_off"); keys = [v.key for v in c._STICKY]
    assert HOTKEY_BIT == 4
    assert t.target({k: None for k in keys}) == dict(zip(keys, ["506", "122", "58"]))  # defaults 510 / 126 / 62 minus the hotkey bit
    assert t.target(dict(zip(keys, ["511", "126", "62"]))) == dict(zip(keys, ["507", "122", "58"]))  # other flags kept
