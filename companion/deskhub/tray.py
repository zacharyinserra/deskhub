"""The companion's icon in the Windows notification area (system tray).

Coloured while the board is connected, grey while it isn't; the tooltip names
the board and its IP. Right-click for Settings, Edit config, Run setup, Restart,
Open log and Quit; double-click opens Settings. Plain Win32 through ctypes, on its own thread with its own window.
"""
import ctypes
import ctypes.wintypes as wt
import io
import logging
import os
import pathlib
import subprocess
import sys
import threading
from typing import Callable

from .pc_power import LRESULT, WNDCLASSW, WNDPROC

log = logging.getLogger(__name__)

WM_APP_TRAY = 0x8000 + 1
WM_NULL = 0x0000
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 1, 2, 4
MF_STRING, MF_SEPARATOR, MF_GRAYED = 0x0, 0x800, 0x1
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x0002, 0x0100

AMBER = (255, 178, 36)
GREY = (107, 113, 124)


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT), ("uFlags", wt.UINT),
                ("uCallbackMessage", wt.UINT), ("hIcon", wt.HICON), ("szTip", wt.WCHAR * 128),
                ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD), ("szInfo", wt.WCHAR * 256),
                ("uVersion", wt.UINT), ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wt.HICON)]


def icon_png(color: tuple[int, int, int], size: int = 32) -> bytes:
    """A small desk display: a rounded screen on a stand, in the given colour."""
    from PIL import Image, ImageDraw

    s = size * 4  # draw large, then shrink for smooth edges
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 16, s - 8, s - 36), radius=18, fill=color)
    d.rounded_rectangle((22, 30, s - 22, s - 50), radius=8, fill=(22, 24, 29, 255))
    d.rectangle((s // 2 - 8, s - 36, s // 2 + 8, s - 18), fill=color)
    d.rounded_rectangle((s // 2 - 34, s - 20, s // 2 + 34, s - 8), radius=6, fill=color)
    buf = io.BytesIO()
    im.resize((size, size), Image.LANCZOS).save(buf, "PNG")
    return buf.getvalue()


class Tray:
    """on_restart and on_quit run on the tray's thread."""

    MENU = [(6, "Settings"), (1, "Edit config"), (2, "Run setup"), (3, "Restart"), (4, "Open log"), (None, None),
            (5, "Quit")]

    def __init__(self, config_path: pathlib.Path, log_file: pathlib.Path | None,
                 on_restart: Callable[[], None], on_quit: Callable[[], None],
                 on_settings: Callable[[], None] | None = None):
        self.config_path = config_path
        self.log_file = log_file
        self.on_restart = on_restart
        self.on_quit = on_quit
        self.on_settings = on_settings or (lambda: os.startfile(self.config_path))
        self.hwnd = None
        self.connected = False
        self.tip = "Desk Hub: starting"
        self._icons = {}
        self._proc = WNDPROC(self._wndproc)
        self._ready = threading.Event()

    # ---- public, from any thread -------------------------------------------

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        threading.Thread(target=self._run, name="tray", daemon=True).start()
        self._ready.wait(5)
        return self.hwnd is not None

    def set_status(self, connected: bool, detail: str):
        self.connected = connected
        self.tip = f"Desk Hub: {detail}"[:127]
        if self.hwnd:
            self._notify(NIM_MODIFY)

    def remove(self):
        if self.hwnd:
            self._notify(NIM_DELETE)

    # ---- the window --------------------------------------------------------

    def _icon(self, connected: bool):
        if connected not in self._icons:
            png = icon_png(AMBER if connected else GREY)
            buf = ctypes.create_string_buffer(png, len(png))
            self._icons[connected] = _user32.CreateIconFromResourceEx(buf, len(png), True, 0x00030000, 32, 32, 0)
        return self._icons[connected]

    def _notify(self, op: int):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_APP_TRAY
        nid.hIcon = self._icon(self.connected)
        nid.szTip = self.tip
        if not _shell32.Shell_NotifyIconW(op, ctypes.byref(nid)) and op != NIM_DELETE:
            log.warning("tray icon update failed")

    def _menu(self):
        menu = _user32.CreatePopupMenu()
        for cmd, text in self.MENU:
            if cmd is None:
                _user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            else:
                grey = cmd == 4 and not (self.log_file and self.log_file.is_file())
                _user32.AppendMenuW(menu, MF_STRING | (MF_GRAYED if grey else 0), cmd, text)
        pt = wt.POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        _user32.SetForegroundWindow(self.hwnd)  # so the menu closes when you click elsewhere
        cmd = _user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self.hwnd, None)
        _user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        _user32.DestroyMenu(menu)
        if cmd:
            self._command(cmd)

    def _command(self, cmd: int):
        try:
            if cmd == 1:
                os.startfile(self.config_path)
            elif cmd == 2:
                # Setup asks questions, so it gets a console of its own.
                py = pathlib.Path(sys.executable).with_name("python.exe")
                subprocess.Popen([str(py if py.is_file() else sys.executable), "-m", "deskhub.setup_cli",
                                  "--config", str(self.config_path)],
                                 cwd=str(self.config_path.parent), creationflags=subprocess.CREATE_NEW_CONSOLE)
            elif cmd == 3:
                self.on_restart()
            elif cmd == 4 and self.log_file:
                os.startfile(self.log_file)
            elif cmd == 5:
                self.remove()
                self.on_quit()
            elif cmd == 6:
                self.on_settings()
        except Exception as e:
            log.warning("tray command failed: %s", e)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_APP_TRAY:
            event = lparam & 0xFFFF
            if event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                self._menu()
            elif event == WM_LBUTTONDBLCLK:
                self._command(6)
            return 0
        if msg == self._taskbar_created:
            self._notify(NIM_ADD)  # Explorer restarted: put the icon back
            return 0
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run(self):
        try:
            hinst = _kernel32.GetModuleHandleW(None)
            wc = WNDCLASSW(lpfnWndProc=self._proc, hInstance=hinst, lpszClassName="DeskHubTray")
            _user32.RegisterClassW(ctypes.byref(wc))
            self._taskbar_created = _user32.RegisterWindowMessageW("TaskbarCreated")
            self.hwnd = _user32.CreateWindowExW(0, "DeskHubTray", "Desk Hub tray", 0, 0, 0, 0, 0,
                                                None, None, hinst, None)
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self._notify(NIM_ADD)
        except Exception as e:
            log.warning("can't show the tray icon: %s", e)
            self.hwnd = None
            self._ready.set()
            return
        self._ready.set()
        msg = wt.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))


if sys.platform == "win32":
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    _kernel32.GetModuleHandleW.restype = wt.HMODULE
    _kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
    _user32.DefWindowProcW.restype = LRESULT
    _user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    _user32.RegisterClassW.restype = wt.ATOM
    _user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    _user32.RegisterWindowMessageW.restype = wt.UINT
    _user32.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
    _user32.CreateWindowExW.restype = wt.HWND
    _user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
    _user32.CreateIconFromResourceEx.restype = wt.HICON
    _user32.CreateIconFromResourceEx.argtypes = [ctypes.c_char_p, wt.DWORD, wt.BOOL, wt.DWORD,
                                                 ctypes.c_int, ctypes.c_int, wt.UINT]
    _user32.CreatePopupMenu.restype = wt.HMENU
    _user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
    _user32.TrackPopupMenu.restype = wt.BOOL
    _user32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wt.HWND, wt.LPVOID]
    _user32.DestroyMenu.argtypes = [wt.HMENU]
    _user32.SetForegroundWindow.argtypes = [wt.HWND]
    _user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    _user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    _user32.GetMessageW.restype = wt.BOOL
    _user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
    _user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
    _user32.DispatchMessageW.restype = LRESULT
    _user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
    _shell32.Shell_NotifyIconW.restype = wt.BOOL
    _shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
