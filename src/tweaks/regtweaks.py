"""Registry tweaks (current user only) built from plain data.

A tweak can change several values at once; its saved state is a dict keyed 'path|name'. Real winreg I/O is
injected so the logic is testable off Windows. Backups are untrusted input: restoring only ever writes the
values this tweak declares, with the declared type, and rejects anything else."""
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional, Tuple
from src.tweaks.engine import Tweak

DWORD, SZ = "dword", "sz"
WIN = lambda: sys.platform == "win32"

@dataclass(frozen=True)
class RegValue:
    path: str          # under HKEY_CURRENT_USER
    name: str
    kind: str          # DWORD or SZ
    target: Any = None  # wanted value (unused when the tweak supplies target_fn)

    def __post_init__(self):
        if self.kind not in (DWORD, SZ): raise ValueError(f"unknown registry kind {self.kind!r}")
        if not self.path or not self.name or "\x00" in self.path + self.name or "|" in self.path + self.name:
            raise ValueError("invalid registry path or value name")

    @property
    def key(self) -> str: return f"{self.path}|{self.name}"

def check_value(rv: RegValue, v: Any) -> Any:
    """None means 'not set'. Anything of the wrong type is refused rather than coerced."""
    if v is None: return None
    if rv.kind == DWORD and isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 0xFFFFFFFF: return v
    if rv.kind == SZ and isinstance(v, str): return v
    raise ValueError(f"unexpected value {v!r} for {rv.name}")

def _win_read(path: str, name: str):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k: return winreg.QueryValueEx(k, name)[0]
    except FileNotFoundError: return None

def _win_write(path: str, name: str, kind: str, val) -> None:
    import winreg
    if val is None:  # restore "not set"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as k: winreg.DeleteValue(k, name)
        except FileNotFoundError: pass
        return
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as k:
        if kind == DWORD: winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(val))
        else: winreg.SetValueEx(k, name, 0, winreg.REG_SZ, str(val))

def clear_flag_bit(cur: Optional[str], bit: int, default: int) -> str:
    """Clear one bit of a flags value stored as a decimal string, keeping every other bit.
    A missing value means Windows uses `default`. Unparseable text raises, so the tweak refuses to touch it."""
    value = default if cur is None else int(cur)
    return str(value & ~bit)

def flags_without_bit(values: Iterable[RegValue], defaults: Dict[str, int], bit: int) -> Callable[[dict], dict]:
    """target_fn for tweaks that switch off one bit in several flag values."""
    vals = tuple(values)
    return lambda orig: {v.key: clear_flag_bit(orig[v.key], bit, defaults[v.key]) for v in vals}

def registry_tweak(id: str, name: str, what: str, why: str, drawbacks: str, values: Iterable[RegValue], category: str = "General",
                   note: str = "", target_fn: Optional[Callable[[dict], dict]] = None,
                   io: Optional[Tuple[Callable, Callable]] = None) -> Tweak:
    rd, wr = io or (_win_read, _win_write)
    vals = tuple(values)
    if not vals: raise ValueError("a registry tweak needs at least one value")
    if target_fn is None:
        if any(v.target is None for v in vals): raise ValueError("every value needs a target (or give target_fn)")
        target: Any = {v.key: check_value(v, v.target) for v in vals}
    else:
        target = target_fn

    def read() -> dict:
        return {v.key: check_value(v, rd(v.path, v.name)) for v in vals}

    def write(state) -> None:
        if not isinstance(state, dict): raise ValueError("saved value is not valid")
        if any(v.key not in state for v in vals): raise ValueError("saved value is incomplete")
        checked = [(v, check_value(v, state[v.key])) for v in vals]  # validate everything before writing anything
        for v, x in checked: wr(v.path, v.name, v.kind, x)

    return Tweak(id, name, what, why, drawbacks, False, True, read, write, target,
                 (lambda: True) if io else WIN, category, note)
