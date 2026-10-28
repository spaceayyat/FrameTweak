import os, re
ROOT = os.path.dirname(os.path.dirname(__file__))
BATS = ["Install-FrameTweak.bat", "Launch-FrameTweak.bat", "Uninstall-FrameTweak.bat", "Build-FrameTweak.bat"]
def read(n): return open(os.path.join(ROOT, n), "rb").read()

def test_scripts_exist_with_crlf():
    for n in BATS:
        b = read(n); assert b and b"\r\n" in b and b"\n" not in b.replace(b"\r\n", b""), n

def test_only_whitelisted_deletions():
    ok = ('"%ROOT%\\.venv"', '"%ROOT%\\build"', '"%ROOT%\\dist"', '"%APPDATA%\\FrameTweak"')
    for n in BATS:
        t = read(n).decode()
        assert not re.search(r"\bdel\b|\berase\b|rd /s|\*\.\*", t, re.I), n
        for line in re.findall(r"rmdir /s /q (.*)", t): assert line.strip() in ok, (n, line)

def test_no_admin_or_downloads():
    for n in BATS:
        t = read(n).decode().lower()
        assert "runas" not in t and "invoke-webrequest" not in t and "curl" not in t and "bitsadmin" not in t

def test_paths_quoted_and_script_relative():
    for n in BATS: assert "%~dp0" in read(n).decode()

def test_spec_and_requirements():
    assert os.path.exists(os.path.join(ROOT, "FrameTweak.spec"))
    assert "pytest" not in open(os.path.join(ROOT, "requirements.txt")).read()
