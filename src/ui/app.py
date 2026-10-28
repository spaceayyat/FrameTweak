import os, re, sys
from PySide6.QtCore import Qt, QTimer, QSettings, QPointF, QRectF, QSize, QPropertyAnimation
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QIcon, QPixmap, QLinearGradient, QBrush, QPainterPath, QFont
from PySide6.QtWidgets import (QSizePolicy, QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
                               QStackedWidget, QLabel, QPushButton, QFrame, QGridLayout, QPlainTextEdit, QComboBox, QGraphicsOpacityEffect, QGraphicsDropShadowEffect)
from src.core import sysinfo
from src.core.applog import get_logger, data_dir, log_path
from src.core.paths import resource_path
from src.monitoring.live import LiveMonitor
from src.startup.inspect_startup import read_startup_entries
from src.startup.manage import is_admin
from src.ui.worker import run_bg, wait_all
from src.ui.pages_system import startup_page, debloat_page
from src.ui.pages import tweaks_page, cleanup_page
from src.ui.pages_gaming import gaming_page
from src.gaming import diagnostics

ACC, DIM = "#22d3ee", "#7d8896"
QSS = f"""
QWidget{{background:#0b0d10;color:#e6edf3;font-family:'Segoe UI';font-size:13px}}
QFrame#header{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0f1318,stop:1 #111a2b)}}
QFrame#glow{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #22d3ee,stop:0.45 #8b5cf6,stop:1 #0b0d10)}}
QLabel#brand{{font-size:15px;font-weight:600;letter-spacing:3px;background:transparent}}
QLabel#pill{{background:#131a22;border:1px solid #243040;border-radius:10px;padding:3px 10px;color:{DIM}}}
QListWidget#nav{{background:#0f1318;border:none;border-right:1px solid #1d252e;padding:10px 8px;outline:0}}
QListWidget#nav::item{{padding:10px 12px;border-radius:8px;margin:2px 0;color:{DIM}}}
QListWidget#nav::item:hover{{background:#151b23;color:#e6edf3}}
QListWidget#nav::item:selected{{background:#0f2530;color:{ACC};border-left:2px solid {ACC}}}
QFrame#card{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #151b23,stop:1 #10151b);border:1px solid #212a34;border-radius:12px}}
QFrame#card:hover{{border:1px solid #1f6f80}}
QFrame#card QLabel{{background:transparent}}
QLabel{{background:transparent}} QLabel#h1{{font-size:20px;font-weight:600}} QLabel#dim{{color:{DIM}}}
QPushButton{{background:transparent;border:1px solid {ACC};color:{ACC};border-radius:8px;padding:7px 16px}}
QPushButton[primary="true"]{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0891b2,stop:1 #6d28d9);border:none;color:white;font-weight:600}}
QPushButton[primary="true"]:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #06b6d4,stop:1 #7c3aed)}}
QPushButton[primary="true"]:disabled{{background:#1a222b;color:#4b5563}}
QPushButton:hover{{background:#0f2a35}} QPushButton:pressed{{background:#133a49}}
QPushButton:focus{{border:1px solid #8b5cf6}} QPushButton:disabled{{border-color:#2a333d;color:#4b5563}}
QTableWidget{{background:#12171d;gridline-color:#1d252e;border:1px solid #212a34;border-radius:8px;selection-background-color:#0f2530}}
QHeaderView::section{{background:#161c24;border:none;padding:6px;color:{DIM}}}
QLineEdit,QComboBox,QPlainTextEdit{{background:#12171d;border:1px solid #243040;border-radius:8px;padding:6px}}
QLineEdit:focus,QComboBox:focus{{border:1px solid {ACC}}}
QScrollBar:vertical{{background:transparent;width:10px}} QScrollBar::handle:vertical{{background:#26303b;border-radius:5px;min-height:30px}}
QScrollBar::add-line,QScrollBar::sub-line{{height:0}} QStatusBar{{background:#0f1318;color:{DIM}}}
QTabWidget::pane{{border:none}} QTabBar::tab{{background:transparent;color:{DIM};padding:8px 18px;border-bottom:2px solid transparent}}
QTabBar::tab:selected{{color:{ACC};border-bottom:2px solid {ACC}}} QTabBar::tab:hover{{color:#e6edf3}}
QProgressBar{{background:#161c24;border:none;border-radius:3px}} QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #22d3ee,stop:1 #8b5cf6);border-radius:3px}}
QCheckBox::indicator,QTableView::indicator{{width:16px;height:16px;border:1px solid #3a4756;border-radius:4px;background:#12171d}}
QCheckBox::indicator:checked,QTableView::indicator:checked{{background:{ACC};border-color:{ACC}}}
QCheckBox::indicator:hover{{border-color:{ACC}}}
QListWidget::item{{padding:7px 8px;border-radius:6px}} QListWidget::item:selected{{background:#0f2530;color:{ACC}}}
QTextBrowser,QListWidget{{background:#12171d;border:1px solid #212a34;border-radius:8px;padding:6px}} QCheckBox{{spacing:8px}}
QToolTip{{background:#161c24;color:#e6edf3;border:1px solid #243040}}
"""

def _pix(name, color):
    pm = QPixmap(40, 40); pm.fill(Qt.transparent); p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.setBrush(Qt.NoBrush)
    poly = lambda pts: p.drawPolyline(QPolygonF([QPointF(*q) for q in pts]))
    {"Dashboard": lambda: [p.drawRect(*r) for r in ((6, 6, 11, 11), (23, 6, 11, 11), (6, 23, 11, 11), (23, 23, 11, 11))],
     "Monitoring": lambda: poly([(5, 26), (14, 26), (19, 10), (25, 32), (30, 20), (35, 20)]),
     "Startup": lambda: (p.drawArc(8, 8, 24, 24, 120 * 16, 300 * 16), p.drawLine(20, 5, 20, 18)),
     "Gaming": lambda: (p.drawRoundedRect(5, 12, 30, 17, 8, 8), p.drawLine(12, 20, 18, 20), p.drawLine(15, 17, 15, 23)),
     "Debloat": lambda: (p.drawRect(9, 12, 22, 22), p.drawLine(6, 9, 34, 9), p.drawLine(16, 5, 24, 5)),
     "Tweaks": lambda: [(p.drawLine(6, y, 34, y), p.drawEllipse(x - 3, y - 3, 6, 6)) for y, x in ((10, 14), (20, 26), (30, 18))],
     "Cleanup": lambda: (p.drawLine(8, 32, 32, 32), p.drawLine(14, 28, 26, 8), p.drawLine(26, 8, 30, 10)),
     "Logs": lambda: [p.drawLine(8, y, 32, y) for y in (10, 20, 30)],
     "Settings": lambda: (p.drawEllipse(12, 12, 16, 16), p.drawEllipse(18, 18, 4, 4))}[name]()
    p.end(); return pm

def glyph(name):
    ic = QIcon(_pix(name, DIM)); ic.addPixmap(_pix(name, ACC), QIcon.Selected); return ic

def card(title, value):
    f = QFrame(); f.setObjectName("card"); l = QVBoxLayout(f)
    t = QLabel(title); t.setObjectName("dim"); v = QLabel(value); v.setWordWrap(True); l.addWidget(t); l.addWidget(v); return f, v

class Chart(QWidget):
    def __init__(self, title, data, color):
        super().__init__(); self.title, self.data, self.color = title, data, QColor(color); self.setMinimumHeight(110)
    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor(DIM)); p.drawText(8, 16, f"{self.title}: {self.data[-1]:.0f}" if self.data else f"{self.title}: Unavailable")
        if len(self.data) < 2: return
        mx = max(1.0, max(self.data)) if self.title.startswith("Disk") else 100.0
        w, h, n = self.width() - 16, self.height() - 34, len(self.data); base = self.height() - 8
        pts = [QPointF(8 + w * i / (n - 1), base - h * v / mx) for i, v in enumerate(self.data)]
        path = QPainterPath(); path.moveTo(pts[0].x(), base)
        for q in pts: path.lineTo(q)
        path.lineTo(pts[-1].x(), base); path.closeSubpath(); g = QLinearGradient(0, 0, 0, self.height()); c1, c2 = QColor(self.color), QColor(self.color); c1.setAlpha(90); c2.setAlpha(0)
        g.setColorAt(0, c1); g.setColorAt(1, c2); p.fillPath(path, QBrush(g)); p.setPen(QPen(self.color, 2)); p.drawPolyline(QPolygonF(pts))

class Gauge(QWidget):
    def __init__(self, label, unit="%"):
        super().__init__(); self.label, self.unit, self.value, self.maxv = label, unit, None, 100.0; self.setMinimumSize(150, 150)
    def set(self, v, maxv=100.0): self.value, self.maxv = v, maxv; self.update()
    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); side = min(self.width(), self.height()) - 36; r = QRectF((self.width() - side) / 2, 10, side, side)
        p.setPen(QPen(QColor("#1b232d"), 10, Qt.SolidLine, Qt.RoundCap)); p.drawArc(r, 225 * 16, -270 * 16)
        if self.value is not None:
            g = QLinearGradient(r.topLeft(), r.bottomRight()); g.setColorAt(0, QColor(ACC)); g.setColorAt(1, QColor("#8b5cf6"))
            p.setPen(QPen(QBrush(g), 10, Qt.SolidLine, Qt.RoundCap)); p.drawArc(r, 225 * 16, int(-270 * 16 * min(1.0, self.value / self.maxv)))
        p.setPen(QColor("#e6edf3")); f = p.font(); f.setPointSize(16); f.setWeight(QFont.DemiBold); p.setFont(f)
        p.drawText(r, Qt.AlignCenter, "N/A" if self.value is None else f"{self.value:.0f}{self.unit}")
        f.setPointSize(9); f.setWeight(QFont.Normal); p.setFont(f); p.setPen(QColor(DIM)); p.drawText(QRectF(0, r.bottom() - 4, self.width(), 24), Qt.AlignCenter, self.label)

def page(sub=None):
    w = QWidget(); l = QVBoxLayout(w)
    if sub: s = QLabel(sub); s.setObjectName("dim"); s.setWordWrap(True); s.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum); l.addWidget(s)
    return w, l

def title(l, t):
    h = QLabel(t); h.setObjectName("h1"); h.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum); l.insertWidget(0, h)

class Window(QMainWindow):
    NAV = ["Dashboard", "Monitoring", "Startup", "Gaming", "Debloat", "Tweaks", "Cleanup", "Logs", "Settings"]
    def __init__(self):
        super().__init__(); self.setWindowTitle("FrameTweak"); self.setWindowIcon(QIcon(resource_path("assets/frametweak.ico")))
        self.log = get_logger(); self.mon = LiveMonitor(); self.cfg = QSettings("FrameTweak", "FrameTweak"); self.resize(1120, 700)
        g = self.cfg.value("geometry")
        if g: self.restoreGeometry(g)
        root = QWidget(); self.setCentralWidget(root); v = QVBoxLayout(root); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0); v.addWidget(self._header()); gl = QFrame(); gl.setObjectName("glow"); gl.setFixedHeight(2); v.addWidget(gl)
        body = QHBoxLayout(); body.setSpacing(0); v.addLayout(body, 1)
        self.nav = QListWidget(); self.nav.setObjectName("nav"); self.nav.setFixedWidth(196); self.nav.setIconSize(QSize(20, 20))
        for n in self.NAV: self.nav.addItem(QListWidgetItem(glyph(n), n))
        body.addWidget(self.nav); self.stack = QStackedWidget(); body.addWidget(self.stack, 1)
        for p in (self._dashboard(), self._monitoring(), startup_page(), gaming_page(), debloat_page(), tweaks_page(), cleanup_page(), self._logs(), self._settings()):
            p.layout().setContentsMargins(24, 18, 24, 14); self.stack.addWidget(p)
        self.nav.currentRowChanged.connect(self._nav); self.nav.setCurrentRow(0)
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(int(self.cfg.value("interval_ms", 1000)))

    def _header(self):
        f = QFrame(); f.setObjectName("header"); f.setFixedHeight(54); h = QHBoxLayout(f); h.setContentsMargins(16, 0, 16, 0)
        ic = QLabel(); ic.setPixmap(QPixmap(resource_path("assets/frametweak.png")).scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)); h.addWidget(ic)
        b = QLabel("FRAMETWEAK"); b.setObjectName("brand"); h.addWidget(b); h.addStretch()
        for t in (sysinfo.windows_version() or "Not Windows", "Administrator" if is_admin() else "Standard user (no admin)"):
            p = QLabel(t); p.setObjectName("pill"); h.addWidget(p, 0, Qt.AlignVCenter)
        return f

    def _nav(self, i):
        self.stack.setCurrentIndex(i); self._fade(self.stack.currentWidget())
        if self.NAV[i] == "Logs": self._load_log()

    def _dashboard(self):
        w, l = page("Read-only analysis. Nothing is changed. Unreadable values show as Unavailable."); title(l, "Dashboard")
        gf = QFrame(); gf.setObjectName("card"); gl = QHBoxLayout(gf); self.g_cpu, self.g_ram, self.g_disk = Gauge("CPU"), Gauge("RAM"), Gauge("Disk MB/s", "")
        for g in (self.g_cpu, self.g_ram, self.g_disk): gl.addWidget(g)
        sh = QGraphicsDropShadowEffect(gf); sh.setBlurRadius(36); sh.setOffset(0, 0); sh.setColor(QColor(34, 211, 238, 55)); gf.setGraphicsEffect(sh); l.addWidget(gf)
        grid = QGridLayout(); l.addLayout(grid); self.cards = {}
        for i, k in enumerate(["Windows", "CPU", "GPU", "RAM", "Disk", "Power plan", "Game Mode", "Startup items"]):
            f, v = card(k, "…"); self.cards[k] = v; grid.addWidget(f, i // 2, i % 2)
        self.warn = QLabel(""); self.warn.setObjectName("dim"); self.warn.setWordWrap(True); l.addWidget(self.warn)
        self.recent = QLabel(""); self.recent.setObjectName("dim"); self.recent.setWordWrap(True); l.addWidget(self.recent)
        self.abtn = QPushButton("Analyze PC"); self.abtn.setProperty("primary", True); self.abtn.clicked.connect(self.analyze); self.abtn.setFixedWidth(140); l.addWidget(self.abtn); l.addStretch()
        self.analyze(); return w

    def analyze(self):
        self.abtn.setEnabled(False); self.statusBar().showMessage("Analyzing…")
        run_bg(lambda: (sysinfo.collect(), len(read_startup_entries())), self._show, lambda m: (self.abtn.setEnabled(True), self.statusBar().showMessage(f"Analysis failed: {m}"), self.log.error("analysis failed: %s", m)))

    def _show(self, res):
        s, n = res; u = lambda x: x if x not in (None, "") else "Unavailable"; c = self.cards
        c["Windows"].setText(u(s.windows) + ("" if s.supported or not s.windows else "  (unsupported version)"))
        c["CPU"].setText(f"{u(s.cpu)} ({s.cpu_cores} threads)" if s.cpu_cores else u(s.cpu)); c["GPU"].setText(u(s.gpu))
        c["RAM"].setText(f"{sysinfo.fmt_bytes(s.ram_available)} free of {sysinfo.fmt_bytes(s.ram_total)}")
        c["Disk"].setText(f"{sysinfo.fmt_bytes(s.disk_free)} free of {sysinfo.fmt_bytes(s.disk_total)}")
        c["Power plan"].setText(u(s.power_plan)); c["Game Mode"].setText("Unavailable" if s.game_mode is None else "On" if s.game_mode else "Off")
        c["Startup items"].setText(str(n) if sys.platform == "win32" else "Unavailable"); self.warn.setText("\n".join(s.notes))
        acts = [x for x in self._log_lines() if re.search(r"tweak|startup|debloat|cleanup", x)][-5:]
        self.recent.setText("Recent actions:\n" + "\n".join(acts) if acts else "Recent actions: none recorded yet.")
        self.abtn.setEnabled(True); self.statusBar().showMessage("Analysis complete", 4000); self.log.info("Analysis run")

    def _monitoring(self):
        w, l = page("Live values sampled at the interval set in Settings. GPU usage and temperature are not implemented."); title(l, "Monitoring")
        self.charts = [Chart("CPU %", self.mon.cpu, ACC), Chart("RAM %", self.mon.ram, "#8b5cf6"), Chart("Disk MB/s", self.mon.disk, "#38bdf8")]
        for c in self.charts: l.addWidget(c)
        self.proc = QLabel(""); self.proc.setObjectName("dim"); self.proc.setWordWrap(True); self.proc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum); l.addWidget(self.proc); return w

    def _tick(self):
        i = self.stack.currentIndex()
        if i not in (0, 1): return  # sample only while a live view is visible
        self.mon.sample()
        if i == 0:
            self.g_cpu.set(self.mon.cpu[-1]); self.g_ram.set(self.mon.ram[-1])
            self.g_disk.set(self.mon.disk[-1] if self.mon.disk else None, max(100.0, max(self.mon.disk)) if self.mon.disk else 100.0); return
        for c in self.charts: c.update()
        self.proc.setText("Top memory users: " + ", ".join(f"{n} ({sysinfo.fmt_bytes(b)})" for n, b in self.mon.top_processes(5)))

    def _fade(self, wdg):
        e = QGraphicsOpacityEffect(wdg); wdg.setGraphicsEffect(e); a = QPropertyAnimation(e, b"opacity", wdg); a.setDuration(160); a.setStartValue(0.0); a.setEndValue(1.0)
        a.finished.connect(lambda: wdg.setGraphicsEffect(None)); a.start(); self._anim = a

    def _log_lines(self):
        try:
            with open(log_path(), encoding="utf-8", errors="replace") as f: return f.read().splitlines()[-300:]
        except OSError: return []

    def _logs(self):
        w, l = page("Local log of analyses and every attempted change. Nothing is uploaded."); title(l, "Logs")
        self.logbox = QPlainTextEdit(); self.logbox.setReadOnly(True); l.addWidget(self.logbox)
        r = QHBoxLayout(); b = QPushButton("Refresh"); b.clicked.connect(self._load_log); r.addWidget(b); r.addStretch(); l.addLayout(r); return w

    def _load_log(self):
        self.logbox.setPlainText("\n".join(self._log_lines()) or "No log entries yet.")

    def _settings(self):
        w, l = page("Preferences are stored locally and restored on the next launch (window size and position are saved automatically)."); title(l, "Settings")
        r = QHBoxLayout(); r.addWidget(QLabel("Monitoring update interval")); cb = QComboBox()
        for lab, ms in (("1 second", 1000), ("2 seconds", 2000), ("5 seconds", 5000)): cb.addItem(lab, ms)
        cb.setCurrentIndex(max(0, cb.findData(int(self.cfg.value("interval_ms", 1000))))); cb.currentIndexChanged.connect(self._set_interval); self.icombo = cb
        r.addWidget(cb); r.addStretch(); l.addLayout(r)
        d = QLabel(f"Data folder: {data_dir()}"); d.setObjectName("dim"); d.setWordWrap(True); d.setTextInteractionFlags(Qt.TextSelectableByMouse); l.addWidget(d)
        r2 = QHBoxLayout(); o = QPushButton("Open data folder"); o.clicked.connect(self._open_data); rs = QPushButton("Reset window size"); rs.clicked.connect(self._reset_geom)
        r2.addWidget(o); r2.addWidget(rs); r2.addStretch(); l.addLayout(r2); l.addStretch(); return w

    def _set_interval(self, _):
        ms = self.icombo.currentData(); self.cfg.setValue("interval_ms", ms); self.timer.setInterval(ms); self.statusBar().showMessage("Saved", 3000)

    def _open_data(self):
        if sys.platform == "win32": os.startfile(data_dir())
        else: self.statusBar().showMessage("Opening folders is only supported on Windows.", 5000)

    def _reset_geom(self): self.cfg.remove("geometry"); self.resize(1120, 700); self.statusBar().showMessage("Window size reset", 3000)

    def closeEvent(self, e):
        self.cfg.setValue("geometry", self.saveGeometry()); self.timer.stop(); diagnostics.CANCEL.set(); wait_all(); super().closeEvent(e)

def run():
    if sys.platform == "win32":
        try:
            import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FrameTweak.App")
        except Exception: pass
    app = QApplication(sys.argv); app.setApplicationName("FrameTweak"); app.setOrganizationName("FrameTweak")
    app.setWindowIcon(QIcon(resource_path("assets/frametweak.ico"))); app.setStyleSheet(QSS)
    w = Window(); w.show(); sys.exit(app.exec())
