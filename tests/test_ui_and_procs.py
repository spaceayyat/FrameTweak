import os, re, sys, glob, time, pytest
from src.core import winproc

def test_winproc_hides_console_on_windows(monkeypatch):
    seen = {}
    class SI:  dwFlags = 0; wShowWindow = 1
    monkeypatch.setattr(winproc.sys, "platform", "win32")
    monkeypatch.setattr(winproc.subprocess, "STARTUPINFO", SI, raising=False)
    monkeypatch.setattr(winproc.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(winproc.subprocess, "run", lambda a, **kw: seen.update(kw, args=a))
    winproc.run(["x"])
    assert seen["creationflags"] == 0x08000000 and seen["shell"] is False and seen["capture_output"] and seen["timeout"] == 10
    assert seen["startupinfo"].wShowWindow == 0

def test_winproc_rejects_strings():
    with pytest.raises(TypeError): winproc.run("cmd /c dir")

def test_no_direct_subprocess_elsewhere():
    root = os.path.dirname(os.path.dirname(__file__))
    for f in glob.glob(root + "/src/**/*.py", recursive=True) + [root + "/main.py"]:
        t = open(f, encoding="utf-8").read()
        if f.endswith("winproc.py"): continue
        assert not re.search(r"subprocess\.(run|Popen|call|check_output)|os\.system|shell=True|os\.popen", t), f

def test_icon_assets_valid():
    from PIL import Image
    root = os.path.dirname(os.path.dirname(__file__))
    ico = Image.open(root + "/assets/frametweak.ico"); assert {16, 32, 256} <= {s[0] for s in ico.info["sizes"]}
    assert Image.open(root + "/assets/frametweak.png").size == (256, 256)
    assert "icon='assets/frametweak.ico'" in open(root + "/FrameTweak.spec").read()

def test_shortcut_targets_app_not_bat():
    root = os.path.dirname(os.path.dirname(__file__))
    t = open(root + "/Install-FrameTweak.bat").read()
    assert "pythonw.exe" in t and "FT_TARGET=%ROOT%\\Launch" not in t

def _app():
    pytest.importorskip("PySide6"); os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication; return QApplication.instance() or QApplication([])

def test_background_worker_delivers_on_ui_thread():
    app = _app(); from PySide6.QtCore import QThread
    from src.ui.worker import run_bg, wait_all
    got = {}
    run_bg(lambda: 41 + 1, lambda r: got.update(r=r, t=QThread.currentThread()))
    run_bg(lambda: 1 / 0, None, lambda m: got.update(e=m))
    end = time.time() + 5
    while ("r" not in got or "e" not in got) and time.time() < end: app.processEvents(); time.sleep(0.01)
    wait_all(); assert got["r"] == 42 and got["t"] is QThread.currentThread() and "division" in got["e"]

def test_main_window_all_pages_and_settings(tmp_path, monkeypatch):
    app = _app(); monkeypatch.setenv("APPDATA", str(tmp_path))
    from src.ui.app import Window, QSS
    app.setStyleSheet(QSS); w = Window(); assert w.stack.count() == len(w.NAV) == 9
    for i in range(w.stack.count()): w.nav.setCurrentRow(i); app.processEvents()
    w.icombo.setCurrentIndex(2); assert w.timer.interval() == 5000 and int(w.cfg.value("interval_ms")) == 5000
    w.cfg.setValue("interval_ms", 1000); w.close()
