"""Run blocking work off the UI thread; results are delivered on the UI thread via a main-thread QObject slot."""
from PySide6.QtCore import QObject, QThread, Signal, Slot

class _Relay(QObject):
    def __init__(self, ok, err): super().__init__(); self._ok, self._err = ok, err
    @Slot(object)
    def on_ok(self, r): self._ok(r)
    @Slot(str)
    def on_err(self, m): (self._err or (lambda _m: None))(m)

class _Worker(QThread):
    ok = Signal(object); err = Signal(str)
    def __init__(self, fn): super().__init__(); self.fn = fn
    def run(self):
        try: self.ok.emit(self.fn())
        except Exception as e: self.err.emit(str(e) or e.__class__.__name__)

_live = set()
def run_bg(fn, on_ok, on_err=None):
    r = _Relay(on_ok, on_err); w = _Worker(fn); w.ok.connect(r.on_ok); w.err.connect(r.on_err)
    item = (w, r); _live.add(item); w.finished.connect(lambda: _live.discard(item)); w.start(); return w

def wait_all(ms=5000):
    for w, _ in list(_live): w.wait(ms)
