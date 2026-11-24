"""What the settings page does beyond saving sections: things that test a connection,
keep a credential in the Windows credential store, read firmware settings, or
build and flash the firmware. Each action takes the page's arguments and returns
JSON for it; ActionError carries a message to show.
"""
import os
import pathlib
import re
import secrets
import subprocess
import sys
import threading

from ..calendars_cli import load, write

FIRMWARE_DIR = pathlib.Path(__file__).resolve().parents[3] / "firmware"
_HEX = re.compile(r"#[0-9a-fA-F]{6}")
_HOST = re.compile(r"[\w.\-:]+")


class ActionError(Exception):
    """A problem to show on the page as is."""


def _text(args: dict, key: str, what: str = "", required: bool = True) -> str:
    value = str(args.get(key) or "").strip()
    if required and not value:
        raise ActionError(f"{what or key} is empty")
    return value


def _color(args: dict, default: str) -> str:
    c = str(args.get("color") or default)
    if not _HEX.fullmatch(c):
        raise ActionError("colour must look like #3a4256")
    return c.lower()


def _index(args: dict, items) -> int:
    try:
        i = int(args.get("index"))
    except (TypeError, ValueError):
        raise ActionError("pick one from the list")
    if not 0 <= i < len(items):
        raise ActionError("that one is gone; reload the page")
    return i


def _keyring():
    import keyring
    return keyring


def _forget(service: str, key: str):
    kr = _keyring()
    try:
        kr.delete_password(service, key)
    except kr.errors.PasswordDeleteError:
        pass


def _ensure_page(doc, page: str):
    """With an explicit [pages] list, a newly configured page has to be in it to show."""
    pages = doc.get("pages")
    enabled = pages.get("enabled") if pages is not None else None
    if enabled is not None and page not in enabled:
        enabled.append(page)


def _status_code(e: Exception):
    return getattr(getattr(e, "response", None), "status_code", None) or type(e).__name__


# ---- keys and hooks -------------------------------------------------------------

def secrets_status(path, args):
    from .. import github, steam_web
    from ..setup_cli import hook_events_installed, hook_events_wanted
    from ..steam import steam_installed

    installed = hook_events_installed()
    try:
        wanted = hook_events_wanted()
    except Exception:
        wanted = installed
    hooks = "missing" if not installed else "current" if installed >= wanted else "old"
    return {"steam_key": bool(steam_web.get_key()), "github_token": bool(github.get_token()),
            "steam_installed": steam_installed(), "hooks": hooks}


def steam_key_set(path, args):
    from .. import steam_web

    key = _text(args, "key", "the key")
    if not re.fullmatch(r"[0-9A-Fa-f]{32}", key):
        raise ActionError("a Steam key is 32 letters and digits")
    try:
        steam_web._http_get(f"{steam_web.API}/ISteamWebAPIUtil/GetSupportedAPIList/v1/", {"key": key})
    except Exception as e:
        raise ActionError(f"Steam didn't accept the key ({_status_code(e)})")
    steam_web.set_key(key)
    return {"message": "Steam key saved. Restart the companion to show friends and playtime.", "restart": True}


def steam_key_remove(path, args):
    from .. import steam_web

    steam_web.set_key(None)
    return {"message": "Steam key removed.", "restart": True}


def github_token_set(path, args):
    from .. import github

    token = _text(args, "token", "the token")
    try:
        cal = github.fetch(token)
    except Exception as e:
        raise ActionError(f"GitHub didn't accept the token ({_status_code(e)})")
    github.set_token(token)
    return {"message": f"Saved. @{cal['login']}: {cal['total']:,} contributions in the last year. "
                       "Put the GitHub widget on Home or turn on the GitHub page to show it.", "restart": True}


def github_token_remove(path, args):
    from .. import github

    github.set_token(None)
    return {"message": "GitHub token removed.", "restart": True}


def hooks_install(path, args):
    from ..setup_cli import INSTALLER

    remove = bool(args.get("remove"))
    r = subprocess.run([sys.executable, str(INSTALLER), "hooks", *(["--remove"] if remove else [])],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    if r.returncode != 0:
        raise ActionError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip()
                          else "the installer failed")
    return {"message": "Hooks removed from Claude Code." if remove else
            "Hooks added. Claude Code sessions you start from now on report to the board."}


# ---- calendars ------------------------------------------------------------------

def calendar_add_link(path, args):
    import httpx
    import icalendar

    from ..calendar_feed import _safe_error
    from ..calendars_cli import feeds_of

    url = _text(args, "url", "the address")
    if not url.startswith(("https://", "http://", "webcal://")):
        raise ActionError("the address starts with https:// or webcal://")
    fetch = "https://" + url[len("webcal://"):] if url.startswith("webcal://") else url
    try:
        r = httpx.get(fetch, follow_redirects=True, timeout=20)
        r.raise_for_status()
        count = len(icalendar.Calendar.from_ical(r.content).walk("VEVENT"))
    except Exception as e:
        raise ActionError(f"couldn't read that address: {_safe_error(e)}")
    name = _text(args, "name", "the name", required=False) or "Calendar"
    doc = load(path)
    row = {"name": name, "url": url, "color": _color(args, "#2dd4bf")}
    import tomlkit

    t = tomlkit.table()
    t.update(row)
    feeds_of(doc).append(t)
    _ensure_page(doc, "calendar")
    write(path, doc)
    return {"message": f"Added {name}: {count} events found.", "restart": True}


def calendar_apple_list(path, args):
    from ..calendar_feed import DEFAULT_CALDAV_URL, _safe_error, caldav_calendars

    user, password = _text(args, "username", "the Apple ID"), _text(args, "password", "the password")
    try:
        found = caldav_calendars(DEFAULT_CALDAV_URL, user, password)
    except Exception as e:
        raise ActionError(f"couldn't connect: {_safe_error(e, password)}")
    if not found:
        raise ActionError("connected, but this account has no calendars")
    return {"calendars": [name for name, _ in found]}


def calendar_apple_add(path, args):
    import tomlkit

    from ..calendar_feed import DEFAULT_CALDAV_URL, KEYRING_SERVICE
    from ..calendars_cli import feeds_of

    found = calendar_apple_list(path, args)["calendars"]
    chosen = [c for c in args.get("calendars") or [] if c in found]
    user, password = args["username"].strip(), args["password"].strip()
    _keyring().set_password(KEYRING_SERVICE, user, password)
    t = tomlkit.table()
    t.update({"type": "caldav", "name": _text(args, "name", required=False) or "iCloud", "url": DEFAULT_CALDAV_URL,
              "username": user, "color": _color(args, "#ff5a5f")})
    if chosen and len(chosen) < len(found):
        t["calendars"] = chosen
    doc = load(path)
    feeds_of(doc).append(t)
    _ensure_page(doc, "calendar")
    write(path, doc)
    return {"message": "Added iCloud. The password is in the Windows credential store.", "restart": True}


def calendar_edit(path, args):
    from ..calendars_cli import feeds_of

    doc = load(path)
    feeds = feeds_of(doc)
    i = _index(args, feeds)
    feeds[i]["name"] = _text(args, "name", "the name")
    feeds[i]["color"] = _color(args, str(feeds[i].get("color", "#7c9cff")))
    write(path, doc)
    return {"message": "Calendar changed.", "restart": True}


def calendar_remove(path, args):
    from ..calendar_feed import KEYRING_SERVICE
    from ..calendars_cli import feeds_of

    doc = load(path)
    feeds = feeds_of(doc)
    i = _index(args, feeds)
    gone = feeds[i]
    user = gone.get("username") if str(gone.get("type", "")).lower() == "caldav" else None
    del feeds[i]
    write(path, doc)
    if user and not any(f.get("username") == user for f in feeds):
        _forget(KEYRING_SERVICE, str(user))
    return {"message": f"Removed {gone.get('name', 'the calendar')}.", "restart": True}


# ---- printers -------------------------------------------------------------------

def printer_add(path, args):
    from .. import bambu_cloud as cloud
    from .. import printer_poll as poll
    from .. import printer_types as ptypes
    from ..calendar_feed import _safe_error
    from ..printer import MAX_PRINTERS, MODELS, lan_key, probe_local
    from ..printers_cli import _same, printers_of

    kind = _text(args, "type", "the brand")
    host = _text(args, "host", "the IP address")
    if not _HOST.fullmatch(host):
        raise ActionError("that doesn't look like an IP address or host name")
    fields = args.get("fields") or {}
    secret = str(args.get("secret") or "").strip() or None
    force = bool(args.get("force"))
    doc = load(path)
    printers = printers_of(doc)
    if len(printers) >= MAX_PRINTERS:
        raise ActionError(f"the board shows at most {MAX_PRINTERS} printers; remove one first")

    if kind == "local":
        serial = str(fields.get("serial", "")).strip().upper()
        if not serial or not secret:
            raise ActionError("the serial number and access code are both needed")
        entry = {"name": "", "type": "local", "serial": serial, "host": host}
        if any(_same(p, entry) for p in printers):
            raise ActionError(f"{serial} is already added")
        try:
            ok, msg = probe_local(host, serial, secret)
        except Exception as e:
            ok, msg = False, f"Connection test failed: {_safe_error(e, secret)}"
        if not ok and not force:
            return {"ok": False, "message": msg}
        entry["name"] = _text(args, "name", required=False) or MODELS.get(serial[:3], "Printer")
        _keyring().set_password(cloud.SERVICE, lan_key(serial), secret)
    elif kind in ptypes.BACKENDS:
        spec = ptypes.module(kind).SPEC
        try:
            port = int(args.get("port") or spec.default_port)
        except ValueError:
            raise ActionError("the port is a number")
        if not 0 < port < 65536:
            raise ActionError("the port is a number from 1 to 65535")
        entry = {"name": "", "type": spec.type, "host": host}
        if port != spec.default_port:
            entry["port"] = port
        if any(_same(p, entry) for p in printers):
            raise ActionError(f"{host} is already added")
        for f in spec.fields:
            value = str(fields.get(f.key) or f.default).strip()
            if not value and f.required:
                raise ActionError(f"{f.prompt} is empty")
            if value:
                entry[f.key] = value
        if spec.secret_required and not secret:
            raise ActionError(f"{(spec.secret_prompt or 'the password').replace(' (hidden)', '')} is empty")
        try:
            res = spec.probe(dict(entry), secret)
        except Exception as e:
            res = poll.ProbeResult(False, f"Connection test failed: {_safe_error(e, secret or '')}")
        if not res.ok and not force:
            return {"ok": False, "message": res.message}
        secret = res.secret or secret
        entry["name"] = _text(args, "name", required=False) or res.name or res.model or spec.default_model
        model = _text(args, "model", required=False) or res.model
        if model and model != spec.default_model:
            entry["model"] = model
        if secret:
            _keyring().set_password(poll.SERVICE, poll.secret_key(spec.type, host, port), secret)
    else:
        raise ActionError(f"no printer type {kind!r}")

    import tomlkit

    row = tomlkit.table()
    row.update(entry)
    printers.append(row)
    _ensure_page(doc, "printer")
    write(path, doc)
    return {"ok": True, "message": f"Added {entry['name']}.", "restart": True}


def printer_remove(path, args):
    from .. import bambu_cloud as cloud
    from .. import printer_poll as poll
    from ..printer import lan_key
    from ..printers_cli import _spec, printers_of

    doc = load(path)
    printers = printers_of(doc)
    i = _index(args, printers)
    gone = dict(printers[i])
    del printers[i]
    write(path, doc)
    spec = _spec(str(gone.get("type", "")))
    if spec:
        _forget(poll.SERVICE, poll.secret_key(spec.type, str(gone.get("host", "")),
                                              int(gone.get("port", spec.default_port))))
    elif gone.get("type") == "local":
        _forget(cloud.SERVICE, lan_key(str(gone.get("serial", ""))))
    elif not any(p.get("account") == gone.get("account") for p in printers):
        _forget(cloud.SERVICE, str(gone.get("account", "")))
    return {"message": f"Removed {gone.get('name', 'the printer')}.", "restart": True}


def open_terminal(path, args):
    """Run one of the terminal tools in a console window: Bambu cloud sign-in asks for an emailed code."""
    tools = {"printers-cloud": ["deskhub.printers_cli", "add-cloud"], "media": ["deskhub.setup_cli", "media"]}
    cmd = tools.get(str(args.get("tool")))
    if not cmd:
        raise ActionError("unknown tool")
    py = pathlib.Path(sys.executable).with_name("python.exe")
    subprocess.Popen([str(py if py.is_file() else sys.executable), "-m", cmd[0], "--config", str(path), *cmd[1:]],
                     cwd=str(pathlib.Path(path).parent),
                     creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0)
    return {"message": "Opened in a new window. Reload this page when you're done there."}


# ---- games ----------------------------------------------------------------------

def windows(path, args):
    from ..games_cli import open_windows, suggest

    return {"windows": [{**w, "suggest": suggest(w)} for w in open_windows()]}


def game_add(path, args):
    import tomlkit

    from ..games_cli import games_of

    name = _text(args, "name", "the name")
    procs = args.get("process") or []
    if isinstance(procs, str):
        procs = [p.strip() for p in procs.split(",") if p.strip()]
    title = _text(args, "title", required=False)
    if not procs and not title:
        raise ActionError("a program name or a window title is needed")
    doc = load(path)
    games = games_of(doc)
    if any(str(g.get("name", "")).lower() == name.lower() for g in games):
        raise ActionError(f'"{name}" is already added')
    row = tomlkit.table()
    row["name"] = name
    if title:
        row["title"] = title
    if procs:
        row["process"] = procs[0] if len(procs) == 1 else procs
    for key in ("image", "launch"):
        value = _text(args, key, required=False).strip('"').replace("\\", "/")
        if value:
            row[key] = value
    games.append(row)
    _ensure_page(doc, "games")
    write(path, doc)
    return {"message": f"Added {name}.", "restart": True}


def game_remove(path, args):
    from ..games_cli import games_of

    doc = load(path)
    games = games_of(doc)
    i = _index(args, games)
    name = games[i].get("name", "the game")
    del games[i]
    write(path, doc)
    return {"message": f"Removed {name}.", "restart": True}


# ---- the board's firmware settings ------------------------------------------------

def _sdkconfig() -> pathlib.Path:
    return FIRMWARE_DIR / "sdkconfig"


def board_read(path, args):
    from ..setup_cli import read_kconfig

    sdk = _sdkconfig()
    if not FIRMWARE_DIR.is_dir():
        return {"available": False}
    text = sdk.read_text(encoding="utf-8") if sdk.is_file() else ""
    get = lambda k: read_kconfig(text, k)  # noqa: E731
    return {"available": True, "built": sdk.is_file(), "ssid": get("HUB_WIFI_SSID") or "",
            "has_password": bool(get("HUB_WIFI_PASSWORD")), "city": get("HUB_CITY") or "",
            "fahrenheit": get("HUB_FAHRENHEIT") == "y", "h24": get("HUB_24H") == "y",
            "screen_off_min": int(get("HUB_SCREEN_OFF_MIN") or 0)}


def geocode(path, args):
    import httpx

    from ..setup_cli import describe_place, geocode as search

    try:
        places = search(_text(args, "query", "the city"))
    except httpx.HTTPError as e:
        raise ActionError(f"city search failed ({type(e).__name__}); check the internet connection")
    return {"places": [{"label": describe_place(p), "name": p["name"], "latitude": p["latitude"],
                        "longitude": p["longitude"], "timezone": p.get("timezone", ""),
                        "country": p.get("country_code", "")} for p in places]}


def board_save(path, args):
    """Write the firmware settings to sdkconfig. They reach the board with the next flash."""
    from ..setup_cli import posix_tz, read_kconfig, set_kconfig

    sdk = _sdkconfig()
    if not FIRMWARE_DIR.is_dir():
        raise ActionError("the firmware folder isn't next to the companion")
    text = sdk.read_text(encoding="utf-8") if sdk.is_file() else ""
    new = text
    ssid = str(args.get("ssid", "")).strip()
    if len(ssid.encode()) > 32:
        raise ActionError("the network name is at most 32 bytes")
    new = set_kconfig(new, "HUB_WIFI_SSID", ssid)
    password = str(args.get("password") or "")
    if password:
        if not 8 <= len(password.encode()) <= 63:
            raise ActionError("Wi-Fi passwords are 8 to 63 characters")
        new = set_kconfig(new, "HUB_WIFI_PASSWORD", password)
    place = args.get("place")
    if place:
        try:
            tz = posix_tz(str(place["timezone"]))
            lat, lon = float(place["latitude"]), float(place["longitude"])
        except (KeyError, TypeError, ValueError):
            raise ActionError("pick the city again")
        new = set_kconfig(new, "HUB_CITY", str(place["name"]))
        new = set_kconfig(new, "HUB_LATITUDE", f"{lat:.4f}")
        new = set_kconfig(new, "HUB_LONGITUDE", f"{lon:.4f}")
        new = set_kconfig(new, "HUB_TZ", tz)
    new = set_kconfig(new, "HUB_FAHRENHEIT", bool(args.get("fahrenheit")))
    new = set_kconfig(new, "HUB_24H", bool(args.get("h24")))
    try:
        minutes = int(args.get("screen_off_min") or 0)
    except ValueError:
        raise ActionError("screen timeout is a number of minutes")
    if not 0 <= minutes <= 240:
        raise ActionError("screen timeout is 0 to 240 minutes")
    new = set_kconfig(new, "HUB_SCREEN_OFF_MIN", minutes)

    # The board and the companion share a token (as setup does it).
    board_token = read_kconfig(text, "HUB_TOKEN")
    token = board_token
    if not token or token == "change-me":
        token = secrets.token_urlsafe(18)
        new = set_kconfig(new, "HUB_TOKEN", token)
    import tomlkit

    doc = load(path)
    hub = doc.setdefault("hub", tomlkit.table())
    if hub.get("token") != token:
        hub["token"] = token
        write(path, doc)
    if new == text:
        return {"changed": False, "message": "Nothing changed."}
    sdk.write_text(new, encoding="utf-8")
    FLASH.board_token = board_token if board_token != token else None
    return {"changed": True, "message": "Saved. The board gets this with new firmware: Build and flash."}


class FlashJob:
    """One build-and-flash at a time, its output kept for the page to show."""

    MAX_LINES = 400

    def __init__(self):
        self.proc = None
        self.lines: list[str] = []
        self.result = None   # None while running or before the first run, else True/False
        self.board_token = None
        self._lock = threading.Lock()

    def start(self, config_path, port: str = "", usb: bool = False):
        with self._lock:
            if self.proc and self.proc.poll() is None:
                raise ActionError("a build is already running")
            self.lines, self.result = [], None
            cmd = [sys.executable, "-m", "deskhub.flash_cli", "--config", str(config_path),
                   "--firmware", str(FIRMWARE_DIR)]
            if port:
                cmd += ["--port", port]
            if usb:
                cmd.append("--usb")
            if self.board_token:
                cmd += ["--board-token", self.board_token]
            env = {**os.environ, "PYTHONUNBUFFERED": "1", "DESKHUB_NO_WINDOW": "1", "PYTHONIOENCODING": "utf-8"}
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         env=env, cwd=str(pathlib.Path(config_path).parent),
                                         creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        threading.Thread(target=self._read, args=(self.proc,), name="flash-output", daemon=True).start()

    def _read(self, proc):
        for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                self.lines.append(line)
                del self.lines[:-self.MAX_LINES]
        self.result = proc.wait() == 0
        if self.result:
            self.board_token = None

    def status(self) -> dict:
        running = bool(self.proc and self.proc.poll() is None) or (self.proc is not None and self.result is None)
        return {"running": running, "ok": self.result, "lines": self.lines[-self.MAX_LINES:]}


FLASH = FlashJob()


def flash_start(path, args):
    FLASH.start(path, port=_text(args, "port", required=False), usb=bool(args.get("usb")))
    return FLASH.status()


def flash_status(path, args):
    return FLASH.status()


ACTIONS = {f.__name__: f for f in (
    secrets_status, steam_key_set, steam_key_remove, github_token_set, github_token_remove, hooks_install,
    calendar_add_link, calendar_apple_list, calendar_apple_add, calendar_edit, calendar_remove,
    printer_add, printer_remove, open_terminal, windows, game_add, game_remove,
    board_read, geocode, board_save, flash_start, flash_status)}
# Actions that change config.toml (the page reloads its copy after them).
WRITES = {"calendar_add_link", "calendar_apple_add", "calendar_edit", "calendar_remove", "printer_add",
          "printer_remove", "game_add", "game_remove", "board_save"}
