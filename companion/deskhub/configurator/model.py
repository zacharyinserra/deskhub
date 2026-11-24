"""What the settings page edits: read from config.toml as plain JSON, checked, and
written back with tomlkit so comments and the layout of the file survive.

Only sections the page changed are rewritten; everything else is left as it was.
"""
import re

import tomlkit

from ..pages import (ALL_PAGES, GRID_COLS, GRID_ROWS, HOME_SIZES, HOME_WIDGETS, NAV_POSITIONS, NIGHT_STYLES,
                     PAGE_LABELS, PC_SLEEP_MODES, enabled_pages, grid_problem, home_grid, home_header,
                     nav_position, night_schedule, night_style, pc_sleep_mode)
from ..shortcuts import ACTIONS, MAX_TILES, combo_problem
from ..shortcuts_cli import ACTIONS as ACTION_HELP, DEFAULT_ICON, ICONS

# The board's navigation glyph for each page (firmware/main/ui.c, s_glyphs).
PAGE_ICONS = {
    "home": "home", "stats": "insights", "ai": "auto_awesome", "calendar": "event", "weather": "wb_sunny",
    "media": "music_note", "printer": "view_in_ar", "shortcuts": "grid_view", "timer": "timer",
    "games": "sports_esports", "network": "public", "github": "commit",
}
WIDGET_ICONS = {
    "clock": "schedule", "claude": "auto_awesome", "events": "event", "weather": "wb_sunny",
    "media": "music_note", "stats": "insights", "printer": "view_in_ar", "game": "sports_esports",
    "net": "public", "github": "commit",
}
_HEX = re.compile(r"#[0-9a-fA-F]{6}")
SECTIONS = ("pages", "home", "tiles", "display", "services")
AGENTS = ("auto", "claude", "codex")
GITHUB_COLORS = ("green", "accent")

# The plain settings on the services page: key -> (table, key in it, default).
SERVICES = {
    "hub_host": ("hub", "host", "deskhub.local"),
    "calendar_days": ("calendar", "days", 7),
    "agent": ("ai", "agent", "auto"),
    "live_limits": ("claude", "live_limits", False),
    "alerts": ("claude", "alerts", True),
    "idle_alert_seconds": ("claude", "idle_alert_seconds", 30),
    "internet": ("internet", "enabled", True),
    "speedtest_hours": ("internet", "speedtest_hours", 0),
    "show_ip": ("internet", "show_ip", False),
    "steam": ("steam", "enabled", True),
    "presets": ("game_presets", "enabled", True),
    "presets_disabled": ("game_presets", "disabled", []),
    "github_colors": ("github", "colors", "green"),
}


def meta() -> dict:
    """Everything the page needs to draw its choices."""
    return {
        "pages": [{"id": p, "label": "Home" if p == "home" else PAGE_LABELS[p], "icon": PAGE_ICONS[p]}
                  for p in ALL_PAGES],
        "nav": list(NAV_POSITIONS),
        "widgets": [{"id": w, "label": HOME_WIDGETS[w], "icon": WIDGET_ICONS[w],
                     "widths": list(HOME_SIZES[w][0]), "heights": list(HOME_SIZES[w][1])} for w in HOME_WIDGETS],
        "grid": {"cols": GRID_COLS, "rows": GRID_ROWS},
        "icons": ICONS,
        "actions": [{"id": a, "help": ACTION_HELP[a][0], "target": ACTION_HELP[a][1], "choices": ACTION_HELP[a][2]}
                    for a in ACTION_HELP],
        "default_icon": DEFAULT_ICON,
        "max_tiles": MAX_TILES,
        "pc_sleep": list(PC_SLEEP_MODES),
        "night_style": list(NIGHT_STYLES),
        "agents": list(AGENTS),
        "github_colors": list(GITHUB_COLORS),
        "presets": [p["name"] for p in _presets()],
        "printer_types": printer_types(),
    }


def _presets():
    from ..game_presets import PRESETS

    return PRESETS


def printer_types() -> list[dict]:
    """Every printer brand the companion can add, with the questions each one asks."""
    from .. import printer_types as ptypes

    out = [{"type": "local", "menu": "Bambu Lab on the local network (LAN)",
            "intro": "Needs the printer's IP address and 8-character access code (Settings > WLAN/Network, or "
                     "Settings > LAN Only Mode) and the serial number (Settings > Device, or the label). "
                     "Newer firmware only allows this with LAN Only Mode or Developer Mode on.",
            "default_port": 0, "ask_port": False, "fields": [{"key": "serial", "prompt": "Serial number",
                                                              "default": "", "required": True}],
            "secret_prompt": "Access code", "secret_required": True},
           {"type": "cloud", "menu": "Bambu Lab through your Bambu account",
            "intro": "Signing in to Bambu asks for a code it emails you, so this one runs in a terminal window.",
            "terminal": True}]
    for kind in ptypes.available():
        spec = ptypes.module(kind).SPEC
        out.append({"type": spec.type, "menu": spec.menu, "intro": spec.intro.split("\n", 1)[-1].strip(),
                    "default_port": spec.default_port, "ask_port": spec.ask_port,
                    "fields": [{"key": f.key, "prompt": f.prompt, "default": f.default, "required": f.required}
                               for f in spec.fields],
                    "secret_prompt": (spec.secret_prompt or "").replace(" (hidden)", "") or None,
                    "secret_required": spec.secret_required})
    return out


def _night_text(cfg: dict) -> str:
    night = night_schedule(cfg)
    if not night:
        return ""
    return "-".join(f"{m // 60:02d}:{m % 60:02d}" for m in night)


def read(cfg: dict) -> dict:
    """The editable settings from a parsed config (a plain dict)."""
    tiles = []
    for t in cfg.get("tiles", []) or []:
        if isinstance(t, dict):
            tiles.append({"label": str(t.get("label", "")), "icon": str(t.get("icon", "apps")),
                          "color": str(t.get("color", "#2b2f3a")), "action": str(t.get("action", "")),
                          "target": str(t.get("target", "")),
                          **({"state": str(t["state"])} if "state" in t else {})})
    return {
        "hub": {"host": str((cfg.get("hub") or {}).get("host", "deskhub.local"))},
        "pages": {"enabled": enabled_pages(cfg), "nav": nav_position(cfg)},
        "home": {"header": home_header(cfg), "grid": home_grid(cfg)},
        "tiles": tiles,
        "display": {"pc_sleep": pc_sleep_mode(cfg), "night": _night_text(cfg), "night_style": night_style(cfg)},
        "services": read_services(cfg),
        # Shown, and changed through actions (they hold credentials or need a test first).
        "lists": {"calendars": [describe_feed(f) for f in (cfg.get("calendar") or {}).get("feeds", []) or []],
                  "printers": [describe_printer(p) for p in cfg.get("printers", []) or []],
                  "games": [describe_game(g) for g in cfg.get("games", []) or []]},
    }


def read_services(cfg: dict) -> dict:
    out = {}
    for name, (table, key, default) in SERVICES.items():
        t = cfg.get(table)
        value = t.get(key, default) if isinstance(t, dict) else default
        if isinstance(default, bool):
            value = bool(value)
        elif isinstance(default, list):
            value = [str(v) for v in value] if isinstance(value, list) else []
        elif isinstance(default, (int, float)) and not isinstance(value, (int, float)):
            value = default
        else:
            value = value if isinstance(default, (int, float)) else str(value)
        out[name] = value
    return out


def describe_feed(f: dict) -> dict:
    """A calendar for the page, without its secret address."""
    kind = "caldav" if str(f.get("type", "")).lower() == "caldav" else "ics"
    url = str(f.get("url", ""))
    host = re.sub(r"^\w+://", "", url).split("/")[0] if url.startswith(("http", "webcal")) else url
    where = (f"iCloud, {f.get('username', '')}: {', '.join(f.get('calendars') or []) or 'all calendars'}"
             if kind == "caldav" else (host or "no address"))
    return {"name": str(f.get("name", "")), "color": str(f.get("color", "#7c9cff")), "kind": kind, "where": where}


def describe_printer(p: dict) -> dict:
    from ..printers_cli import describe

    return {"name": str(p.get("name", "")), "type": str(p.get("type", "")), "where": describe(p)}


def describe_game(g: dict) -> dict:
    from ..games_cli import describe

    name = str(g.get("name", ""))
    text = describe(g)
    return {"name": name, "where": text[len(name) + 2:] if text.startswith(f"{name}: ") else text}


# ---- checks -------------------------------------------------------------------

def problems(state: dict) -> dict[str, list[str]]:
    """Why each section can't be saved, by section name (only sections with problems)."""
    out: dict[str, list[str]] = {}

    if "pages" in state:
        p = state["pages"]
        bad = [str(x) for x in p.get("enabled", []) if x not in ALL_PAGES]
        errs = [f"no page called {x!r}" for x in bad]
        if p.get("nav") not in NAV_POSITIONS:
            errs.append(f"navigation bar must be {', '.join(NAV_POSITIONS)}")
        if errs:
            out["pages"] = errs

    if "home" in state:
        grid = state["home"].get("grid", [])
        try:
            items = [{"widget": str(g["widget"]), "x": int(g["x"]), "y": int(g["y"]),
                      "w": int(g["w"]), "h": int(g["h"])} for g in grid]
        except (KeyError, TypeError, ValueError):
            out["home"] = ["a widget is missing its place or size"]
        else:
            errs = grid_problem(items)
            if errs:
                out["home"] = errs

    if "tiles" in state:
        errs = []
        tiles = state["tiles"]
        if len(tiles) > MAX_TILES:
            errs.append(f"at most {MAX_TILES} tiles")
        for i, t in enumerate(tiles, 1):
            name = t.get("label") or f"tile {i}"
            action, target = t.get("action"), str(t.get("target", "")).strip()
            if action not in ACTIONS:
                errs.append(f"{name}: pick what it does")
                continue
            choices = ACTION_HELP[action][2]
            if choices and target not in choices:
                errs.append(f"{name}: pick {', '.join(choices)}")
            elif action in ("keys", "run", "open") and not target:
                errs.append(f"{name}: {ACTION_HELP[action][1].split(',')[0].lower()} is empty")
            elif action == "keys":
                why = combo_problem(target)
                if why:
                    errs.append(f"{name}: {why}")
            if t.get("icon") not in ICONS:
                errs.append(f"{name}: pick an icon")
            if not _HEX.fullmatch(str(t.get("color", ""))):
                errs.append(f"{name}: colour must look like #3a4256")
        if errs:
            out["tiles"] = errs

    if "display" in state:
        d = state["display"]
        errs = []
        if d.get("pc_sleep") not in PC_SLEEP_MODES:
            errs.append(f"while the PC sleeps: {', '.join(PC_SLEEP_MODES)}")
        if d.get("night_style") not in NIGHT_STYLES:
            errs.append(f"night style: {', '.join(NIGHT_STYLES)}")
        night = str(d.get("night", "")).strip()
        if night and not night_schedule({"display": {"night": night}}):
            errs.append("night mode times look like 23:00-07:00")
        if errs:
            out["display"] = errs

    if "services" in state:
        s = state["services"]
        errs = []
        host = str(s.get("hub_host", "")).strip()
        if not host or " " in host or "/" in host:
            errs.append("the board's address is a host name or IP, like deskhub.local or 192.168.1.50")
        if s.get("agent") not in AGENTS:
            errs.append(f"AI page: {', '.join(AGENTS)}")
        if s.get("github_colors") not in GITHUB_COLORS:
            errs.append("GitHub colours: green or accent")
        for key, lo, hi, what in (("calendar_days", 1, 60, "calendar days ahead"),
                                  ("idle_alert_seconds", 0, 3600, "seconds before a finished session alerts"),
                                  ("speedtest_hours", 0, 168, "hours between speed tests")):
            v = s.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
                errs.append(f"{what}: a number from {lo} to {hi}")
        from ..game_presets import PRESETS

        names = {p["name"] for p in PRESETS}
        unknown = [n for n in s.get("presets_disabled", []) if n not in names]
        if unknown:
            errs.append(f"no built-in game called {', '.join(unknown)}")
        if errs:
            out["services"] = errs
    return out


# ---- writing ------------------------------------------------------------------

def _table(doc, name: str):
    if name not in doc:
        doc[name] = tomlkit.table()
    return doc[name]


def _set(table, key: str, value):
    """Set a key only when it changes, so untouched values keep their formatting."""
    if key not in table or table[key] != value:
        table[key] = value


def _write_pages(doc, p: dict):
    pages = _table(doc, "pages")
    order = ["home"] + [x for x in p["enabled"] if x != "home"]
    if pages.get("enabled") != order:
        arr = tomlkit.array()
        arr.extend(order)
        pages["enabled"] = arr
    if p["nav"] != "left" or "nav" in pages:
        _set(pages, "nav", p["nav"])


def _write_home(doc, h: dict):
    home = _table(doc, "home")
    _set(home, "header", bool(h.get("header", True)))
    grid = [{"widget": g["widget"], "x": int(g["x"]), "y": int(g["y"]), "w": int(g["w"]), "h": int(g["h"])}
            for g in sorted(h["grid"], key=lambda g: (int(g["y"]), int(g["x"])))]
    if home.get("grid") != grid:
        arr = tomlkit.array()
        for g in grid:
            t = tomlkit.inline_table()
            t.update(g)
            arr.append(t)
        arr.multiline(True)
        home["grid"] = arr
    for old in ("left", "right"):   # replaced by the grid
        if old in home:
            del home[old]


def _write_tiles(doc, tiles: list[dict]):
    clean = []
    for t in tiles:
        c = {"label": str(t.get("label", "")).strip(), "icon": t["icon"], "color": t["color"].lower(),
             "action": t["action"], "target": str(t.get("target", "")).strip()}
        if ACTION_HELP[c["action"]][1] is None:
            c["target"] = ""
        if "state" in t:
            c["state"] = str(t["state"])
        clean.append(c)
    if doc.get("tiles") == clean:
        return
    aot = tomlkit.aot()
    for c in clean:
        aot.append(tomlkit.item(c))
    doc["tiles"] = aot


def _write_display(doc, d: dict):
    disp = _table(doc, "display")
    _set(disp, "pc_sleep", d["pc_sleep"])
    night = str(d.get("night", "")).strip()
    if night:
        start, end = night_schedule({"display": {"night": night}})
        text = f"{start // 60:02d}:{start % 60:02d}-{end // 60:02d}:{end % 60:02d}"
        if _night_text({"display": dict(disp)}) != text:
            disp["night"] = text
    elif "night" in disp:
        del disp["night"]
    if d["night_style"] != "off" or "night_style" in disp:
        _set(disp, "night_style", d["night_style"])


def _write_services(doc, s: dict):
    current = read_services(doc.unwrap())
    for name, (table, key, default) in SERVICES.items():
        value = s.get(name, default)
        if isinstance(default, int) and not isinstance(default, bool) and float(value).is_integer():
            value = int(value)   # 7, not 7.0
        if name == "hub_host":
            value = str(value).strip()
        if value == current[name] and (table in doc and key in doc[table] or value == default):
            continue   # unchanged, or a default nobody wrote down
        t = _table(doc, table)
        if isinstance(value, list):
            arr = tomlkit.array()
            arr.extend(value)
            value = arr
        t[key] = value


_WRITERS = {"pages": _write_pages, "home": _write_home, "tiles": _write_tiles, "display": _write_display,
            "services": _write_services}


def apply(text: str, state: dict) -> tuple[str, list[str]]:
    """config.toml's text with the given sections written in. Returns the new text
    and the sections that changed. Check problems() first."""
    doc = tomlkit.parse(text)
    before = read(doc.unwrap())
    changed = []
    for name in SECTIONS:
        if name in state and state[name] != before[name]:
            _WRITERS[name](doc, state[name])
            changed.append(name)
    return tomlkit.dumps(doc), changed
