import html
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QMessageBox, QTabWidget, QTextBrowser,
                               QProgressBar, QListWidget, QListWidgetItem, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog)
from src.backup.store import BackupStore
from src.core.applog import data_dir, get_logger
from src.gaming import diagnostics as dg
from src.profiles.store import ProfileStore, KNOWN, compare_snapshots
from src.tweaks import engine
from src.tweaks.catalog import catalog
from src.ui.worker import run_bg

DIMC = "#7d8896"
def _row(*ws):
    r = QHBoxLayout()
    for x in ws: r.addWidget(x)
    r.addStretch(); return r

def _report(s, findings):
    d = s.get("display"); g = s.get("gpu"); t = s.get("temps")
    fmt = lambda v, u="": "Unavailable" if v is None else f"{v}{u}"
    rows = [("Sample", f"{s['seconds']} s at {s['time']}"), ("CPU", f"avg {fmt(s['cpu_avg'], '%')} / peak {fmt(s['cpu_max'], '%')}"),
            ("RAM", f"avg {fmt(s['ram_avg'], '%')} / peak {fmt(s['ram_max'], '%')}"), ("Disk", f"avg {fmt(s['disk_avg'], ' MB/s')} / peak {fmt(s['disk_max'], ' MB/s')}"),
            ("GPU", f"{g['name']}: {g['util']}% use, {g['temp']} °C, {g['mem_used_mb']}/{g['mem_total_mb']} MB (single reading)" if g else "Unavailable (only NVIDIA via nvidia-smi is read)"),
            ("Temperatures", ", ".join(f"{k} {v:.0f} °C" for k, v in t.items()) if t else "Unavailable (no sensors exposed to Windows)"),
            ("Display", f"{d['width']}×{d['height']} @ {d['hz']} Hz" if d and d.get("hz") else (f"{d['width']}×{d['height']}, refresh rate unavailable" if d else "Unavailable")),
            ("Game Mode", {True: "On", False: "Off", None: "Unavailable"}[s.get("game_mode")]), ("Power plan", s.get("power_plan") or "Unavailable"),
            ("Top CPU", ", ".join(f"{html.escape(n)} {v}%" for n, v in s["top_cpu"]) or "Unavailable"),
            ("Top memory", ", ".join(f"{html.escape(n)} {v / 1048576:.0f} MB" for n, v in s["top_ram"]) or "Unavailable")]
    h = "<h3 style='color:#22d3ee'>Measured</h3><table cellpadding=3>" + "".join(f"<tr><td style='color:{DIMC}'>{a}</td><td>{b}</td></tr>" for a, b in rows) + "</table>"
    h += "<h3 style='color:#22d3ee'>Findings (evidence, not verdicts)</h3>"
    col = {"watch": "#f59e0b", "info": "#22d3ee", "ok": "#34d399"}
    for f in findings: h += f"<p><b style='color:{col[f['level']]}'>{html.escape(f['title'])}</b><br>{html.escape(f['evidence'])}<br><span style='color:{DIMC}'>{html.escape(f['note'])}</span></p>"
    return h + f"<p style='color:{DIMC}'>FPS is not measured by FrameTweak. An FPS tool such as in-game counters is needed for that.</p>"

def gaming_page():
    log = get_logger(); store = ProfileStore(data_dir()); bk = BackupStore(data_dir()); st = {"snap": None, "findings": []}
    w = QWidget(); l = QVBoxLayout(w); h = QLabel("Gaming"); h.setObjectName("h1"); l.addWidget(h)
    sub = QLabel("Measured diagnostics, saved profiles and before/after comparisons. No FPS is measured and no result is guaranteed."); sub.setObjectName("dim"); sub.setWordWrap(True); l.addWidget(sub)
    tabs = QTabWidget(); l.addWidget(tabs, 1); msg = QLabel(""); msg.setObjectName("dim"); msg.setWordWrap(True); l.addWidget(msg)
    # ---- Diagnostics
    d = QWidget(); dl = QVBoxLayout(d); run = QPushButton("Run 10-second diagnostic"); run.setProperty("primary", True)
    label = QLineEdit(); label.setPlaceholderText("Label, e.g. Before tweaks"); save = QPushButton("Save to history"); save.setEnabled(False)
    bar = QProgressBar(); bar.setRange(0, 0); bar.setTextVisible(False); bar.setFixedHeight(6); bar.hide()
    out = QTextBrowser(); out.setHtml(f"<p style='color:{DIMC}'>Tip: start the diagnostic, then return to your running game for the 10 seconds. Running it at idle only shows background load.</p>")
    dl.addLayout(_row(run, label, save)); dl.addWidget(bar); dl.addWidget(out)
    def done(s):
        st["snap"], st["findings"] = s, dg.analyze(s); out.setHtml(_report(s, st["findings"])); run.setEnabled(True); bar.hide(); save.setEnabled(True); msg.setText("Diagnostic complete.")
    def fail(m): run.setEnabled(True); bar.hide(); msg.setText(f"Diagnostic failed: {m}"); log.error("diagnostic failed: %s", m)
    def go(): run.setEnabled(False); save.setEnabled(False); bar.show(); msg.setText("Sampling…"); run_bg(dg.collect, done, fail)
    def do_save():
        s = dict(st["snap"], label=label.text().strip() or "Unlabeled"); store.add_history(s); msg.setText(f"Saved “{s['label']}” to history."); hist(); log.info("snapshot saved: %s", s["label"])
    run.clicked.connect(go); save.clicked.connect(do_save); tabs.addTab(d, "Diagnostics")
    # ---- Profiles
    p = QWidget(); pl = QHBoxLayout(p); lst = QListWidget(); lst.setFixedWidth(260); lst.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); pl.addWidget(lst); right = QVBoxLayout(); pl.addLayout(right, 1)
    det = QTextBrowser(); right.addWidget(det, 1); ap = QPushButton("Apply profile…"); ap.setProperty("primary", True); ex = QPushButton("Export…"); im = QPushButton("Import…"); de = QPushButton("Delete")
    right.addLayout(_row(ap, ex, im, de)); nm, exe, notes = QLineEdit(), QLineEdit(), QLineEdit(); nm.setPlaceholderText("New profile name"); exe.setPlaceholderText("Game exe (optional), e.g. game.exe"); notes.setPlaceholderText("Notes")
    checks = {k: QCheckBox(v) for k, v in KNOWN.items()}; rec = QCheckBox("Include last diagnostic findings"); sv = QPushButton("Save profile")
    right.addWidget(nm); right.addWidget(exe); right.addWidget(notes)
    for c in checks.values(): right.addWidget(c)
    right.addWidget(rec); right.addLayout(_row(sv))
    meta = {t.id: t for t in catalog()}
    def cur(): it = lst.currentItem(); return it.data(Qt.UserRole) if it else None
    def plist():
        lst.clear()
        try: ps = store.all()
        except Exception as e: msg.setText(f"Profiles unreadable: {e}"); ps = store.presets()
        for q in ps:
            it = QListWidgetItem(q["name"] + ("  (preset)" if q.get("preset") else "")); it.setData(Qt.UserRole, q); lst.addItem(it)
        lst.setCurrentRow(0)
    def show():
        q = cur(); de.setEnabled(bool(q) and not q.get("preset")); ex.setEnabled(bool(q)); ap.setEnabled(bool(q and q["tweaks"]))
        if not q: return
        t = "".join(f"<li><b>{html.escape(meta[i].name)}</b>: {html.escape(meta[i].what)}<br><span style='color:{DIMC}'>Drawback: {html.escape(meta[i].drawbacks)}</span></li>" for i in q["tweaks"])
        r = "".join(f"<li>{html.escape(x)}</li>" for x in q.get("recommendations", []))
        det.setHtml(f"<h3 style='color:#22d3ee'>{html.escape(q['name'])}</h3><p>{html.escape(q.get('exe') or 'All games')}</p><p>Exact changes:</p><ul>{t}</ul><p style='color:{DIMC}'>{html.escape(q.get('notes', ''))}</p>" + (f"<p>Saved recommendations:</p><ul>{r}</ul>" if r else ""))
    def apply_p():
        q = cur()
        if QMessageBox.question(w, "Apply profile", "These exact changes will be applied, each backed up and verified:\n\n" + "\n".join("• " + meta[i].name for i in q["tweaks"])) != QMessageBox.Yes: return
        res = []
        for i in q["tweaks"]:
            r = engine.apply(meta[i], bk); log.info("profile %s tweak %s -> %s: %s", q["name"], i, r.ok, r.message); res.append(f"{meta[i].name}: {r.message}")
        msg.setText("\n".join(res))
    def save_p():
        try:
            store.save({"name": nm.text(), "exe": exe.text().strip(), "notes": notes.text(), "tweaks": [k for k, c in checks.items() if c.isChecked()],
                        "recommendations": [f["title"] for f in st["findings"]][:10] if rec.isChecked() else []}); msg.setText("Profile saved."); plist()
        except ValueError as e: msg.setText(f"Not saved: {e}")
    def exp():
        f, _ = QFileDialog.getSaveFileName(w, "Export profile", cur()["name"] + ".json", "JSON (*.json)")
        if f:
            try: store.export(cur()["name"], f); msg.setText("Exported.")
            except (OSError, ValueError) as e: msg.setText(f"Export failed: {e}")
    def imp():
        f, _ = QFileDialog.getOpenFileName(w, "Import profile", "", "JSON (*.json)")
        if f:
            try: msg.setText(f"Imported “{store.import_file(f)['name']}” (validated, never executed)."); plist()
            except (OSError, ValueError) as e: msg.setText(f"Import rejected: {e}")
    def dele():
        if QMessageBox.question(w, "Delete", f"Delete profile “{cur()['name']}”?") == QMessageBox.Yes: store.delete(cur()["name"]); plist()
    lst.currentRowChanged.connect(lambda _: show()); ap.clicked.connect(apply_p); sv.clicked.connect(save_p); ex.clicked.connect(exp); im.clicked.connect(imp); de.clicked.connect(dele); tabs.addTab(p, "Profiles")
    # ---- History / before-after
    hw = QWidget(); hl = QVBoxLayout(hw); tb = QTableWidget(0, 7); tb.verticalHeader().setVisible(False); tb.setHorizontalHeaderLabels(["Time", "Label", "CPU avg", "RAM avg", "Disk MB/s", "Game Mode", "Power plan"])
    tb.setSelectionBehavior(QTableWidget.SelectRows); tb.setSelectionMode(QTableWidget.ExtendedSelection); tb.setEditTriggers(QTableWidget.NoEditTriggers); tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    cmp_b, del_b = QPushButton("Compare two selected"), QPushButton("Delete selected"); cmp_b.setProperty("primary", True); res = QTextBrowser(); hl.addWidget(tb); hl.addLayout(_row(cmp_b, del_b)); hl.addWidget(res)
    res.setHtml(f"<p style='color:{DIMC}'>Save two diagnostics (e.g. before and after a tweak), select both and compare. Differences are measured system load, not FPS, and can reflect what was running rather than the tweak.</p>")
    snaps = []
    def hist():
        snaps[:] = sorted(store.history(), key=lambda s: s["time"]); tb.setRowCount(len(snaps)); u = lambda v: "Unavailable" if v is None else str(v)
        for r, s in enumerate(snaps):
            for c, v in enumerate([s["time"], s.get("label", ""), u(s.get("cpu_avg")), u(s.get("ram_avg")), u(s.get("disk_avg")), {True: "On", False: "Off", None: "Unavailable"}[s.get("game_mode")], s.get("power_plan") or "Unavailable"]): tb.setItem(r, c, QTableWidgetItem(v))
    def sel(): return sorted({i.row() for i in tb.selectedIndexes()})
    def compare():
        r = sel()
        if len(r) != 2: msg.setText("Select exactly two rows."); return
        a, b = snaps[r[0]], snaps[r[1]]
        res.setHtml(f"<h3 style='color:#22d3ee'>{html.escape(a.get('label', ''))} → {html.escape(b.get('label', ''))}</h3><table cellpadding=4><tr><th></th><th>Before</th><th>After</th><th>Change</th></tr>" + "".join(f"<tr><td style='color:{DIMC}'>{html.escape(x)}</td><td>{html.escape(y)}</td><td>{html.escape(z)}</td><td>{html.escape(c)}</td></tr>" for x, y, z, c in compare_snapshots(a, b)) + f"</table><p style='color:{DIMC}'>Measured over short samples; not an FPS result.</p>")
    def delh():
        r = sel()
        if r and QMessageBox.question(w, "Delete", f"Delete {len(r)} history entr{'y' if len(r) == 1 else 'ies'}?") == QMessageBox.Yes: store.delete_history([snaps[i]["time"] for i in r]); hist()
    cmp_b.clicked.connect(compare); del_b.clicked.connect(delh); tabs.addTab(hw, "History")
    try: hist()
    except Exception as e: msg.setText(f"History unreadable: {e}")
    plist(); return w
