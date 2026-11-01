import html
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame, QPushButton, QHBoxLayout, QMessageBox,
                               QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QApplication)
from src.backup.store import BackupStore
from src.core.applog import data_dir, get_logger
from src.core import sysinfo
from src.tweaks import engine
from src.tweaks.catalog import catalog, CATEGORIES
from src.cleanup import cleaner
from src.ui.worker import run_bg

def _head(l, title, sub):
    h = QLabel(title); h.setObjectName("h1"); l.addWidget(h)
    s = QLabel(sub); s.setObjectName("dim"); s.setWordWrap(True); l.addWidget(s)

STATE_COLOR = {True: "#34d399", False: "#7d8896", None: "#f59e0b"}
STATE_TEXT = {True: "Applied", False: "Not applied", None: "Unavailable"}

def tweaks_page():
    log, store = get_logger(), BackupStore(data_dir())
    w = QWidget(); l = QVBoxLayout(w)
    _head(l, "Tweaks", "Each change is individually approved, backed up first, verified after applying, and undoable. Nothing needs administrator rights.")
    top = QHBoxLayout(); ua = QPushButton("Undo all applied changes…"); top.addWidget(ua); top.addStretch(); l.addLayout(top)
    status = QLabel(""); status.setWordWrap(True); status.setObjectName("dim")
    holder = QWidget(); body = QVBoxLayout(holder); body.setContentsMargins(0, 0, 0, 0)
    sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.NoFrame); sc.setWidget(holder)
    l.addWidget(sc, 1); l.addWidget(status)
    def card(t, pending):
        f = QFrame(); f.setObjectName("card"); fl = QVBoxLayout(f)
        try: cur = html.escape(engine.format_value(t.read())) if t.supported() else "Unavailable"
        except Exception: cur = "Unavailable"
        applied = engine.is_applied(t); e = html.escape
        txt = (f"<b>{e(t.name)}</b> &nbsp; <span style='color:{STATE_COLOR[applied]}'>{STATE_TEXT[applied]}</span><br>Changes: {e(t.what)}<br>Why: {e(t.why)}<br>Drawbacks: {e(t.drawbacks)}<br>"
               f"Administrator: {'required' if t.needs_admin else 'not required'} | Reversible: {'yes' if t.reversible else 'no'} | "
               f"Current value: {cur}" + (f"<br>After applying: {e(t.note)}" if t.note else "") + ("" if t.supported() else "<br><i>Not supported on this system.</i>"))
        lab = QLabel(txt); lab.setWordWrap(True); lab.setTextFormat(Qt.RichText); fl.addWidget(lab)
        row = QHBoxLayout(); a = QPushButton("Apply"); u = QPushButton("Undo"); a.setEnabled(t.supported() and applied is not True); u.setEnabled(pending)
        a.clicked.connect(lambda _=0, t=t: run(t, True)); u.clicked.connect(lambda _=0, t=t: run(t, False))
        row.addWidget(a); row.addWidget(u); row.addStretch(); fl.addLayout(row); return f
    def render():
        while body.count():
            it = body.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        tweaks = catalog(); pending = {b["id"] for b in _safe_pending(store)}; ua.setEnabled(any(t.id in pending for t in tweaks))
        for cat in sorted({t.category for t in tweaks}, key=lambda c: CATEGORIES.index(c) if c in CATEGORIES else len(CATEGORIES)):
            head = QLabel(cat.upper()); head.setObjectName("dim"); body.addWidget(head)
            for t in tweaks:
                if t.category == cat: body.addWidget(card(t, t.id in pending))
        body.addStretch()
    def run(t, do_apply):
        q = QMessageBox.question(w, "Confirm", f"{'Apply' if do_apply else 'Undo'}: {t.name}?\n\n{t.what}")
        if q != QMessageBox.Yes: return
        r = engine.apply(t, store) if do_apply else engine.undo(t, store)
        log.info("tweak %s %s -> %s: %s", "apply" if do_apply else "undo", t.id, r.ok, r.message)
        status.setText(f"{t.name}: {r.message}"); render()
    def undo_everything():
        pend = {b["id"] for b in _safe_pending(store)}; todo = [t for t in catalog() if t.id in pend]
        if not todo: status.setText("Nothing to undo."); return
        if QMessageBox.question(w, "Confirm", "Restore the original values saved before these changes:\n\n" + "\n".join("• " + t.name for t in todo)) != QMessageBox.Yes: return
        results = engine.undo_all(todo, store)
        for name, r in results: log.info("tweak undo-all %s -> %s: %s", name, r.ok, r.message)
        status.setText("\n".join(f"{name}: {r.message}" for name, r in results)); render()
    ua.clicked.connect(undo_everything)
    render(); return w

def _safe_pending(store):
    try: return store.pending()
    except Exception: return []

def cleanup_page():
    log = get_logger(); w = QWidget(); l = QVBoxLayout(w)
    _head(l, "Cleanup", "Only temporary locations and rebuildable caches. Files modified in the last 24 hours and locked files are left alone. Downloads, documents, browsers and game saves are never touched. Shader caches start unselected: they are rebuilt automatically, but games may stutter on their next launch.")
    t = QTableWidget(0, 3); t.verticalHeader().setVisible(False); t.setHorizontalHeaderLabels(["Category", "Reclaimable", "Files"]); t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch); l.addWidget(t)
    status = QLabel("Click Analyze to measure reclaimable space."); status.setObjectName("dim"); status.setWordWrap(True)
    ab, cb = QPushButton("Analyze"), QPushButton("Clean selected"); cb.setEnabled(False)
    row = QHBoxLayout(); row.addWidget(ab); row.addWidget(cb); row.addStretch(); l.addLayout(row); l.addWidget(status)
    cats = cleaner.categories(); allowed = [c.path for c in cats]; last = [""]  # result of the last clean, shown above the rescan status
    if not cats: status.setText("No cleanup locations found on this system.")
    def scan():  # runs off the UI thread
        out = []
        for c in cats:
            try: out.append(cleaner.analyze(c.path, allowed))
            except Exception as e: out.append((0, 0)); log.warning("analyze %s failed: %s", c.id, e)
        return out
    def show(res):
        t.setRowCount(len(cats)); total = 0
        for r, (c, (size, n)) in enumerate(zip(cats, res)):
            total += size
            it = QTableWidgetItem(c.name); it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked if n and c.default_selected else Qt.Unchecked)
            if c.note: it.setToolTip(c.note)
            t.setItem(r, 0, it); t.setItem(r, 1, QTableWidgetItem(sysinfo.fmt_bytes(size))); t.setItem(r, 2, QTableWidgetItem(str(n)))
        status.setText((last[0] + "\n" if last[0] else "") + f"Estimated reclaimable: {sysinfo.fmt_bytes(total)} (an estimate; locked files may remain)."); last[0] = ""; ab.setEnabled(True); cb.setEnabled(bool(cats))
    def failed(m): ab.setEnabled(True); cb.setEnabled(bool(cats)); status.setText(f"Cleanup failed: {m}"); log.error("cleanup failed: %s", m)
    def analyze():
        if not cats: return
        status.setText((last[0] + "\n" if last[0] else "") + "Analyzing…"); ab.setEnabled(False); cb.setEnabled(False); run_bg(scan, show, failed)
    def do_clean():
        sel = [c for r, c in enumerate(cats) if t.item(r, 0) and t.item(r, 0).checkState() == Qt.Checked]
        if not sel: status.setText("Nothing selected."); return
        if QMessageBox.question(w, "Confirm cleanup", "Permanently delete old files in:\n" + "\n".join(c.path for c in sel)) != QMessageBox.Yes: return
        def work():  # runs off the UI thread
            tot = skipped = 0
            for c in sel:
                try: r = cleaner.clean(c.path, allowed); tot += r.bytes_removed; skipped += r.skipped; log.info("cleanup %s removed=%d skipped=%d", c.id, r.bytes_removed, r.skipped)
                except Exception as e: log.error("cleanup %s failed: %s", c.id, e)
            return tot, skipped
        def done(res):
            last[0] = f"Removed {sysinfo.fmt_bytes(res[0])} (measured). {res[1]} file(s) in use were skipped."; analyze()
        status.setText("Cleaning…"); ab.setEnabled(False); cb.setEnabled(False); run_bg(work, done, failed)
    ab.clicked.connect(analyze); cb.clicked.connect(do_clean); return w
