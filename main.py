import sys

def _msg(text: str) -> None:
    try:
        import ctypes; ctypes.windll.user32.MessageBoxW(0, text, "FrameTweak", 0x10)
    except Exception:
        print(text, file=sys.stderr)

def main() -> None:
    try:
        from src.ui.app import run
        run()
    except Exception as e:
        import traceback
        try:
            from src.core.applog import get_logger; get_logger().error("Startup failure: %s", traceback.format_exc())
        except Exception: pass
        _msg(f"FrameTweak could not start:\n{e}\n\nDetails are in %APPDATA%\\FrameTweak\\frametweak.log")
        sys.exit(1)

if __name__ == "__main__":
    main()
