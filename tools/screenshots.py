"""Regenerates docs/screenshots/*.png headlessly: QT_QPA_PLATFORM=offscreen python tools/screenshots.py
NOTE: run on a non-Windows machine the Windows-specific fields show 'Unavailable' (by design)."""
import os, sys, tempfile, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["APPDATA"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton, QTabWidget
from src.ui.app import Window, QSS
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "screenshots")
app = QApplication(sys.argv); app.setStyleSheet(QSS); QSettings("FrameTweak", "FrameTweak").clear()
w = Window(); w.resize(1150, 740); w.show()
def spin(t):
    end = time.time() + t
    while time.time() < end: app.processEvents(); time.sleep(0.02)
def shot(name): spin(0.4); w.grab().save(os.path.join(OUT, name + ".png")); print("saved", name)
def click(text, root=None):
    for b in (root or w.stack.currentWidget()).findChildren(QPushButton):
        if b.text().startswith(text): b.click(); return
spin(2.5); w._tick(); w._tick(); shot("dashboard")
w.nav.setCurrentRow(1)
for _ in range(25): w._tick(); spin(0.05)
shot("monitoring")
w.nav.setCurrentRow(3); spin(0.3); click("Run 10-second"); spin(12.5); shot("gaming-diagnostics")
w.stack.currentWidget().findChild(QTabWidget).setCurrentIndex(1); shot("gaming-profiles")
w.nav.setCurrentRow(5); shot("tweaks")
w.nav.setCurrentRow(6); spin(0.3); click("Analyze"); spin(2); shot("cleanup")
w.nav.setCurrentRow(4); shot("debloat")
w.close()
