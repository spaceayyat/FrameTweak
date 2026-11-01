"""Real, individually applied tweaks. Only HKCU/powercfg; nothing needs admin or touches security."""
import re, sys
from src.core import winproc
from src.tweaks.engine import Tweak
from src.tweaks.regtweaks import DWORD, SZ, RegValue, flags_without_bit, registry_tweak

WIN = lambda: sys.platform == "win32"
GAMEBAR = r"Software\Microsoft\GameBar"
GAMEDVR = r"Software\Microsoft\Windows\CurrentVersion\GameDVR"
CONFIGSTORE = r"System\GameConfigStore"
MOUSE = r"Control Panel\Mouse"
ACCESS = r"Control Panel\Accessibility"
PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
ADINFO = r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo"
CDM = r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
GUID = re.compile(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
CATEGORIES = ("Gaming", "Input", "Visuals", "Privacy")  # display order on the Tweaks page
SIGN_OUT = "Sign out and back in for it to take effect."

def _reg_read(path, name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k: return winreg.QueryValueEx(k, name)[0]
    except FileNotFoundError: return None

def _reg_write(path, name, val):
    import winreg
    if val is None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as k: winreg.DeleteValue(k, name)
        except FileNotFoundError: pass
    else:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as k: winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(val))

def _powercfg(*args):
    r = winproc.run(["powercfg", *args], timeout=10)
    if r.returncode != 0: raise RuntimeError(r.stderr.strip() or "powercfg failed")
    return r.stdout

def power_read():
    m = GUID.search(_powercfg("/getactivescheme"));
    if not m: raise RuntimeError("Active power plan not found")
    return m.group(0).lower()

def power_write(guid):
    if not isinstance(guid, str) or not GUID.fullmatch(guid): raise ValueError("Invalid power plan id")
    _powercfg("/setactive", guid)

def high_perf_available():
    try: return HIGH_PERF in _powercfg("/list").lower()
    except Exception: return False

# Accessibility "keyboard shortcut is active" flag (SKF_/FKF_/TKF_HOTKEYACTIVE) and each value's Windows default.
HOTKEY_BIT = 0x4
_STICKY = (RegValue(ACCESS + r"\StickyKeys", "Flags", SZ), RegValue(ACCESS + r"\Keyboard Response", "Flags", SZ),
           RegValue(ACCESS + r"\ToggleKeys", "Flags", SZ))
_STICKY_DEFAULTS = {_STICKY[0].key: 510, _STICKY[1].key: 126, _STICKY[2].key: 62}

def catalog():
    return [
        Tweak("game_mode", "Enable Windows Game Mode",
              "Sets HKCU\\Software\\Microsoft\\GameBar\\AutoGameModeEnabled to 1.",
              "Game Mode asks Windows to prioritise the foreground game and limit some background activity.",
              "Gains vary and are often small. Undo restores the exact previous state (including 'not set').",
              False, True, lambda: _reg_read(GAMEBAR, "AutoGameModeEnabled"),
              lambda v: _reg_write(GAMEBAR, "AutoGameModeEnabled", v), 1, WIN, category="Gaming"),
        Tweak("power_high", "Use the High performance power plan",
              "Runs powercfg /setactive for the built-in High performance plan.",
              "Avoids aggressive CPU down-clocking, which can reduce stutter on some desktops.",
              "Higher power use and heat; on laptops it shortens battery life. Plan may not exist on some PCs (then unavailable).",
              False, True, power_read, power_write, HIGH_PERF, lambda: WIN() and high_perf_available(), category="Gaming"),
        registry_tweak("game_dvr_off", "Turn off Game DVR background capture",
              "Sets HKCU\\System\\GameConfigStore\\GameDVR_Enabled and HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\GameDVR\\AppCaptureEnabled to 0.",
              "Stops the Xbox Game Bar's background capture feature, which can add some load while a game runs.",
              "Game Bar clips, screenshots and 'record that' stop working. Gains vary and are often small. Undo restores the exact previous values (including 'not set').",
              [RegValue(CONFIGSTORE, "GameDVR_Enabled", DWORD, 0), RegValue(GAMEDVR, "AppCaptureEnabled", DWORD, 0)], category="Gaming"),
        registry_tweak("gamebar_quiet", "Stop the controller button and tips from opening Game Bar",
              "Sets HKCU\\Software\\Microsoft\\GameBar\\UseNexusForGameBarEnabled and ShowStartupPanel to 0.",
              "Stops the Xbox controller's Guide button from opening Game Bar on top of your game, and hides Game Bar's first-run tips panel.",
              "You can no longer open Game Bar with the controller button (it can still be opened from the keyboard). This does not change performance by itself.",
              [RegValue(GAMEBAR, "UseNexusForGameBarEnabled", DWORD, 0), RegValue(GAMEBAR, "ShowStartupPanel", DWORD, 0)], category="Gaming"),
        registry_tweak("mouse_accel_off", "Turn off mouse pointer acceleration",
              "Sets HKCU\\Control Panel\\Mouse\\MouseSpeed, MouseThreshold1 and MouseThreshold2 to \"0\" (the 'Enhance pointer precision' option).",
              "Pointer movement then follows your hand movement directly instead of depending on how fast you move, which many shooter players prefer for consistent aim. Many games read raw mouse input and ignore this setting.",
              "The desktop pointer feels different, and quick flicks travel less far until you adjust the pointer speed. Undo restores the exact previous values.",
              [RegValue(MOUSE, "MouseSpeed", SZ, "0"), RegValue(MOUSE, "MouseThreshold1", SZ, "0"), RegValue(MOUSE, "MouseThreshold2", SZ, "0")],
              category="Input", note=SIGN_OUT),
        registry_tweak("sticky_keys_prompts_off", "Stop the Sticky Keys and Filter Keys pop-ups",
              "Clears the 'keyboard shortcut is active' flag in HKCU\\Control Panel\\Accessibility (StickyKeys, Keyboard Response and ToggleKeys \\Flags). Every other flag you have set is kept.",
              "Stops the pop-up that appears when Shift is pressed five times, right Shift is held for 8 seconds, or Num Lock is held for 5 seconds, which can pull you out of a full-screen game.",
              "Those keyboard shortcuts no longer start the accessibility features; you can still switch them on in Settings > Accessibility. Undo restores the exact previous values.",
              _STICKY, category="Input", note=SIGN_OUT, target_fn=flags_without_bit(_STICKY, _STICKY_DEFAULTS, HOTKEY_BIT)),
        registry_tweak("transparency_off", "Turn off transparency effects",
              "Sets HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize\\EnableTransparency to 0.",
              "Turns off the see-through blur on the taskbar, Start and windows, so the desktop has slightly less to draw.",
              "Windows looks flatter. The difference is usually small and mostly noticeable on weak integrated graphics.",
              [RegValue(PERSONALIZE, "EnableTransparency", DWORD, 0)], category="Visuals"),
        registry_tweak("ad_id_off", "Turn off the advertising ID",
              "Sets HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo\\Enabled to 0.",
              "Stops Windows giving apps an advertising ID that is used to personalise ads across apps.",
              "Ads shown inside apps stay but become less personalised. No performance effect.",
              [RegValue(ADINFO, "Enabled", DWORD, 0)], category="Privacy"),
        registry_tweak("tips_ads_off", "Turn off Windows suggestions and tips",
              "Sets these HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager values to 0: SubscribedContent-338388Enabled, SubscribedContent-338389Enabled, SubscribedContent-353694Enabled, SubscribedContent-353696Enabled, SystemPaneSuggestionsEnabled, SoftLandingEnabled.",
              "Stops Windows promoting apps and tips in Start, Settings and notifications.",
              "You no longer see Microsoft's suggestions and tips. Windows updates may turn some of these back on. No meaningful performance effect.",
              [RegValue(CDM, n, DWORD, 0) for n in ("SubscribedContent-338388Enabled", "SubscribedContent-338389Enabled", "SubscribedContent-353694Enabled",
                                                    "SubscribedContent-353696Enabled", "SystemPaneSuggestionsEnabled", "SoftLandingEnabled")],
              category="Privacy"),
    ]
