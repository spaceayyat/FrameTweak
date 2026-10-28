from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame, QPushButton, QHBoxLayout, QMessageBox,
                               QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QApplication)
from src.backup.store import BackupStore
from src.core.applog import data_dir, get_logger
from src.core import sysinfo
from src.tweaks import engine
from src.tweaks.catalog import catalog
from src.cleanup import cleaner

def _head(l, title, sub):
    h = QLabel(title); h.setObjectName("h1"); l.addWidget(h)
    s = QLabel(sub); s.setObjectName("dim"); s.setWordWrap(True); l.addWidget(s)

def tweaks_page():
    log, store = get_logger(), BackupStore(data_dir())
    w = QWidget(); l = QVBoxLayout(w)
    _head(l, "Tweaks", "Each change is individually approved, backed up first, verified after applying, and undoable. Nothing needs administrator rights.")
    status = QLabel(""); status.setWordWrap(True); status.setObjectName("dim")
    body = QVBoxLayout(); l.addLayout(body); l.addWidget(status); l.addStretch()
    def render():
        while body.count():
            it = body.takeAt(0); it.widget().deleteLater() if it.widget() else None
        for t in catalog():
            f = QFrame(); f.setObjectName("card"); fl = QVBoxLayout(f)
            try: cur = repr(t.read()) if t.supported() else "Unavailable"
            except Exception: cur = "Unavailable"
            pending = any(b["id"] == t.id for b in _safe_pending(store))
            txt = (f"<b>{t.name}</b><br>Changes: {t.what}<br>Why: {t.why}<br>Drawbacks: {t.drawbacks}<br>"
                   f"Administrator: {'required' if t.needs_admin else 'not required'} | Reversible: {'yes' if t.reversible else 'no'} | "
                   f"Current value: {cur}" + ("" if t.supported() else "<br><i>Not supported on this system.</i>"))
            lab = QLabel(txt); lab.setWordWrap(True); lab.setTextFormat(Qt.RichText); fl.addWidget(lab)
            row = QHBoxLayout(); a = QPushButton("Apply"); u = QPushButton("Undo"); a.setEnabled(t.supported()); u.setEnabled(pending)
            a.clicked.connect(lambda _=0, t=t: run(t, True)); u.clicked.connect(lambda _=0, t=t: run(t, False))
            row.addWidget(a); row.addWidget(u); row.addStretch(); fl.addLayout(row); body.addWidget(f)
    def run(t, do_apply):
        q = QMessageBox.question(w, "Confirm", f"{'Apply' if do_apply else 'Undo'}: {t.name}?\n\n{t.what}")
        if q != QMessageBox.Yes: return
        r = engine.apply(t, store) if do_apply else engine.undo(t, store)
        log.info("tweak %s %s -> %s: %s", "apply" if do_apply else "undo", t.id, r.ok, r.message)
        status.setText(f"{t.name}: {r.message}"); render()
    render(); return w

def _safe_pending(store):
    try: return store.pending()
    except Exception: return []

def cleanup_page():
    log = get_logger(); w = QWidget(); l = QVBoxLayout(w)
    _head(l, "Cleanup", "Only temporary locations. Files modified in the last 24 hours and locked files are left alone. Downloads, documents, browsers and game saves are never touched.")
    t = QTableWidget(0, 3); t.verticalHeader().setVisible(False); t.setHorizontalHeaderLabels(["Category", "Reclaimable", "Files"]); t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch); l.addWidget(t)
    status = QLabel("Click Analyze to measure reclaimable space."); status.setObjectName("dim"); status.setWordWrap(True)
    ab, cb = QPushButton("Analyze"), QPushButton("Clean selected"); cb.setEnabled(False)
    row = QHBoxLayout(); row.addWidget(ab); row.addWidget(cb); row.addStretch(); l.addLayout(row); l.addWidget(status)
    cats = cleaner.categories(); allowed = [c.path for c in cats]
    if not cats: status.setText("No cleanup locations found on this system.")
    def analyze():
        status.setText("Analyzing…"); QApplication.processEvents(); t.setRowCount(len(cats)); total = 0
        for r, c in enumerate(cats):
            try: size, n = cleaner.analyze(c.path, allowed); total += size
            except Exception as e: size, n = 0, 0; log.warning("analyze %s failed: %s", c.id, e)
            it = QTableWidgetItem(c.name); it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked if n else Qt.Unchecked); t.setItem(r, 0, it)
            t.setItem(r, 1, QTableWidgetItem(sysinfo.fmt_bytes(size))); t.setItem(r, 2, QTableWidgetItem(str(n)))
        status.setText(f"Estimated reclaimable: {sysinfo.fmt_bytes(total)} (an estimate; locked files may remain)."); cb.setEnabled(bool(cats))
    def do_clean():
        sel = [c for r, c in enumerate(cats) if t.item(r, 0) and t.item(r, 0).checkState() == Qt.Checked]
        if not sel: status.setText("Nothing selected."); return
        if QMessageBox.question(w, "Confirm cleanup", "Permanently delete old temporary files in:\n" + "\n".join(c.path for c in sel)) != QMessageBox.Yes: return
        tot = skipped = 0
        for c in sel:
            try: r = cleaner.clean(c.path, allowed); tot += r.bytes_removed; skipped += r.skipped; log.info("cleanup %s removed=%d skipped=%d", c.id, r.bytes_removed, r.skipped)
            except Exception as e: log.error("cleanup %s failed: %s", c.id, e)
        status.setText(f"Removed {sysinfo.fmt_bytes(tot)} (measured). {skipped} file(s) in use were skipped."); analyze()
    ab.clicked.connect(analyze); cb.clicked.connect(do_clean); return w
