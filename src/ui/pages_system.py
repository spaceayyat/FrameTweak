from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QMessageBox,
                               QTableWidget, QTableWidgetItem, QHeaderView, QApplication)
from src.backup.store import BackupStore
from src.core.applog import data_dir, get_logger
from src.tweaks import engine
from src.startup.inspect_startup import read_startup_entries
from src.startup.manage import make_tweak
from src.debloat import appx
from src.ui.worker import run_bg

def _head(l, t, s):
    h = QLabel(t); h.setObjectName("h1"); l.addWidget(h); d = QLabel(s); d.setObjectName("dim"); d.setWordWrap(True); l.addWidget(d)

def startup_page():
    log, store = get_logger(), BackupStore(data_dir()); w = QWidget(); l = QVBoxLayout(w); entries = []
    _head(l, "Startup", "Disabling stops an entry launching at sign-in; nothing is deleted or uninstalled. Unknown entries are not necessarily unwanted. All-users (HKLM) entries need FrameTweak run as administrator.")
    t = QTableWidget(0, 4); t.verticalHeader().setVisible(False); t.setHorizontalHeaderLabels(["Name", "Source", "Status", "Command"]); t.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
    t.setSelectionBehavior(QTableWidget.SelectRows); t.setEditTriggers(QTableWidget.NoEditTriggers); l.addWidget(t)
    st = QLabel(""); st.setObjectName("dim"); st.setWordWrap(True)
    row = QHBoxLayout(); bd, be, bu, br = (QPushButton(x) for x in ("Disable selected", "Enable selected", "Restore original", "Refresh"))
    for b in (bd, be, bu, br): row.addWidget(b)
    row.addStretch(); l.addLayout(row); l.addWidget(st)
    def refresh():
        entries[:] = read_startup_entries(); t.setRowCount(len(entries))
        for r, e in enumerate(entries):
            for c, v in enumerate([e.name, e.source, e.status, e.command]): t.setItem(r, c, QTableWidgetItem(v))
        if not entries: st.setText("No startup entries found (or not running on Windows).")
    def sel():
        r = t.currentRow(); return entries[r] if 0 <= r < len(entries) else None
    def act(kind):
        e = sel()
        if not e: st.setText("Select an entry first."); return
        tw = make_tweak(e, enable=(kind == "enable"))
        if QMessageBox.question(w, "Confirm", f"{tw.name}\n\n{tw.what}\n\nDrawback: {tw.drawbacks}") != QMessageBox.Yes: return
        r = engine.undo(tw, store) if kind == "undo" else engine.apply(tw, store)
        log.info("startup %s %s -> %s: %s", kind, tw.id, r.ok, r.message); st.setText(f"{e.name}: {r.message}"); refresh()
    bd.clicked.connect(lambda: act("disable")); be.clicked.connect(lambda: act("enable")); bu.clicked.connect(lambda: act("undo")); br.clicked.connect(refresh)
    refresh(); return w

def debloat_page():
    note = [""]; log = get_logger(); w = QWidget(); l = QVBoxLayout(w)
    _head(l, "Debloat", "Only a curated list of optional Microsoft Store apps can be removed (current user), and only if actually installed. Removing apps does not guarantee higher FPS, and some may return after Windows updates. Security, Store, Xbox/gaming and system components are never offered.")
    top = QHBoxLayout(); scan_b = QPushButton("Scan installed apps"); q = QLineEdit(); q.setPlaceholderText("Search…"); top.addWidget(scan_b); top.addWidget(q, 1); l.addLayout(top)
    t = QTableWidget(0, 6); t.verticalHeader().setVisible(False); t.setHorizontalHeaderLabels(["Remove", "App", "Publisher", "Category", "Size", "Method"]); t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    t.setSortingEnabled(True); t.setEditTriggers(QTableWidget.NoEditTriggers); l.addWidget(t)
    info = QLabel("Click “Scan installed apps” to begin."); info.setWordWrap(True); info.setObjectName("dim")
    rb = QPushButton("Remove selected…"); rb.setEnabled(False); ra = QPushButton("Remove all recommended…"); ra.setEnabled(False)
    br = QHBoxLayout(); br.addWidget(ra); br.addWidget(rb); br.addStretch(); l.addWidget(info); l.addLayout(br)
    def fill():
        info.setText("Scanning…"); scan_b.setEnabled(False); run_bg(appx.scan, show, lambda m: (scan_b.setEnabled(True), info.setText(f"Scan failed: {m}")))
    def show(apps):
        scan_b.setEnabled(True); t.setSortingEnabled(False); t.setRowCount(len(apps))
        for r, a in enumerate(apps):
            c0 = QTableWidgetItem(); c0.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled if a.removable else Qt.NoItemFlags); c0.setCheckState(Qt.Unchecked); c0.setData(Qt.UserRole, a)
            t.setItem(r, 0, c0)
            for c, v in enumerate([a.label, a.publisher, a.category, "Unavailable", a.method], 1): t.setItem(r, c, QTableWidgetItem(v))
        t.setSortingEnabled(True); rb.setEnabled(any(a.removable for a in apps)); ra.setEnabled(rb.isEnabled())
        info.setText((f"{len(apps)} apps found; {sum(a.removable for a in apps)} removable." if apps else "No apps found (this needs Windows 10/11).") + ("\n" + note[0] if note[0] else "")); note[0] = ""
    def filt(txt):
        for r in range(t.rowCount()): t.setRowHidden(r, bool(txt) and txt.lower() not in " ".join(t.item(r, c).text().lower() for c in range(1, 4)))
    def chosen(): return [t.item(r, 0).data(Qt.UserRole) for r in range(t.rowCount()) if t.item(r, 0).checkState() == Qt.Checked]
    def remove():
        sel = chosen()
        if not sel: info.setText("Nothing selected."); return
        msg = "\n".join(f"• {a.label}: {a.explanation}" for a in sel)
        if QMessageBox.question(w, "Confirm removal", f"Remove for the current user:\n\n{msg}\n\nThis can't be undone automatically (reinstall from the Microsoft Store).") != QMessageBox.Yes: return
        res = []
        for a in sel:
            r = appx.remove(a); log.info("debloat %s -> %s: %s", a.name, r.ok, r.message); res.append(f"{a.label}: {r.message}")
        note[0] = "\n".join(res); fill()
    def remove_all():
        for r in range(t.rowCount()):
            if t.item(r, 0).flags() & Qt.ItemIsUserCheckable: t.item(r, 0).setCheckState(Qt.Checked)
        remove()  # still shows the full list and asks for one confirmation
    ra.clicked.connect(remove_all); scan_b.clicked.connect(fill); q.textChanged.connect(filt); rb.clicked.connect(remove); return w
