"""Which board pages are shown. Home is always on."""
import logging
import re

from .steam import steam_installed

log = logging.getLogger(__name__)

ALL_PAGES = ["home", "stats", "ai", "calendar", "weather", "media", "printer", "shortcuts", "timer", "games", "network",
             "github"]
PAGE_LABELS = {
    "stats": "PC stats", "ai": "AI agent usage", "calendar": "Calendar", "weather": "Weather",
    "media": "Now playing", "printer": "3D printer", "shortcuts": "Shortcuts",
    "timer": "Timer", "games": "Games", "network": "Internet (a view on the Stats page)",
    "github": "GitHub contributions",
}


# The navigation bar's order without a [pages] list: Shortcuts last, by the status icons.
DEFAULT_ORDER = [p for p in ALL_PAGES if p != "shortcuts"] + ["shortcuts"]


def enabled_pages(cfg: dict) -> list[str]:
    """Page names to show, in navigation bar order: Home first, then the order of
    [pages] enabled (unknown names and repeats dropped). Without a [pages] block everything is on except
    the printer page (on once a printer is configured), the games page (on when Steam
    is installed or [[games]] are configured) and the GitHub page (on when its widget is
    on Home)."""
    pages = cfg.get("pages")
    if not isinstance(pages, dict) or not isinstance(pages.get("enabled"), list):
        want = {p for p in ALL_PAGES if p not in ("printer", "games", "github")}
        if cfg.get("printers"):
            want.add("printer")
        if steam_installed() or cfg.get("games"):
            want.add("games")
        if any(g["widget"] == "github" for g in home_grid(cfg)):
            want.add("github")
        return [p for p in DEFAULT_ORDER if p == "home" or p in want]
    order = ["home"]
    for name in (str(p).lower() for p in pages["enabled"]):
        if name in ALL_PAGES and name not in order:
            order.append(name)
    return order


NAV_POSITIONS = ("left", "right", "bottom")


def nav_position(cfg: dict) -> str:
    """Where the board's navigation bar goes: [pages] nav = "left" (default),
    "right" or "bottom"."""
    nav = str((cfg.get("pages") or {}).get("nav", "left")).strip().lower()
    return nav if nav in NAV_POSITIONS else "left"


PC_SLEEP_MODES = ("off", "clock", "none")


def pc_sleep_mode(cfg: dict) -> str:
    """What the board does while the PC's display sleeps: [display] pc_sleep =
    "off" (screen dark, default), "clock" (a screensaver clock) or "none"."""
    mode = str((cfg.get("display") or {}).get("pc_sleep", "off")).strip().lower()
    return mode if mode in PC_SLEEP_MODES else "off"


NIGHT_STYLES = ("off", "clock")


def parse_hhmm(text: str) -> int | None:
    """"23:00", "7:30", "7" or "7pm" -> minutes after midnight, or None."""
    m = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?\s*", str(text).lower())
    if not m:
        return None
    h, mins, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ampm:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ampm.startswith("p") else 0)
    if h > 23 or mins > 59:
        return None
    return h * 60 + mins


def night_schedule(cfg: dict) -> tuple[int, int] | None:
    """[display] night = "23:00-07:00": (start, end) in minutes, or None when off."""
    raw = str((cfg.get("display") or {}).get("night", "")).strip()
    if "-" not in raw:
        return None
    a, b = raw.split("-", 1)
    start, end = parse_hhmm(a), parse_hhmm(b)
    if start is None or end is None or start == end:
        return None
    return start, end


def night_style(cfg: dict) -> str:
    """[display] night_style = "off" (screen dark, default) or "clock"."""
    style = str((cfg.get("display") or {}).get("night_style", "off")).strip().lower()
    return style if style in NIGHT_STYLES else "off"


def layout_message(cfg: dict) -> dict:
    # The board restarts when "nav" changes, so it always gets one.
    night = night_schedule(cfg)
    # "ordered": the board lays out its tabs in the order of "pages" (older companions
    # sent them in a fixed order, which the board ignores).
    return {"type": "layout", "pages": enabled_pages(cfg), "ordered": True, "nav": nav_position(cfg),
            "pc_sleep": pc_sleep_mode(cfg),
            # Always sent, so removing the schedule turns night mode off on the board.
            "night_start": night[0] if night else -1, "night_end": night[1] if night else -1,
            "night_style": night_style(cfg)}


# Home screen widgets, placed in two columns top to bottom. "events" stretches to
# fill its column. The left column is wider (the big clock fits there).
HOME_WIDGETS = {
    "clock": "Clock and date",
    "claude": "Claude limits",
    "events": "Up next (calendar)",
    "weather": "Weather",
    "media": "Now playing",
    "stats": "PC stats",
    "printer": "3D print progress",
    "game": "Game",
    "net": "Internet",
    "github": "GitHub contributions",
}
# Defaults with the slim top bar (the default): the clock widget isn't needed.
DEFAULT_LEFT = ["claude", "events"]


def home_columns(cfg: dict) -> tuple[list[str], list[str]]:
    home = cfg.get("home") if isinstance(cfg.get("home"), dict) else {}
    right_default = ["weather", "media", "printer"] if cfg.get("printers") else ["weather", "media", "stats"]

    def column(key, default):
        value = home.get(key)
        if not isinstance(value, list):
            return list(default)
        return [w for w in (str(x).lower() for x in value) if w in HOME_WIDGETS]

    left = column("left", DEFAULT_LEFT)
    right = [w for w in column("right", right_default) if w not in left]
    return left, right


def home_header(cfg: dict) -> bool:
    """True: time and date in a slim bar across the top instead of the clock widget."""
    home = cfg.get("home") if isinstance(cfg.get("home"), dict) else {}
    return bool(home.get("header", True))


# ---- the 5 x 3 grid ----------------------------------------------------------
GRID_COLS, GRID_ROWS = 5, 3
# Sizes each widget supports: (widths, heights), in grid cells.
HOME_SIZES = {
    "clock": (range(2, 6), range(1, 3)),
    "claude": (range(1, 6), range(1, 2)),
    "events": (range(2, 6), range(1, 4)),
    "weather": (range(1, 6), range(1, 2)),
    "media": (range(2, 6), range(1, 2)),
    "stats": (range(1, 6), range(1, 2)),
    "printer": (range(2, 6), range(1, 2)),
    "game": (range(2, 6), range(1, 2)),
    "net": (range(1, 6), range(1, 2)),
    "github": (range(2, 6), range(1, 3)),
}


def widget_sizes(name: str) -> list[str]:
    """Sizes a widget supports, like ["2x1", "3x1"]."""
    ws, hs = HOME_SIZES[name]
    return [f"{w}x{h}" for h in hs for w in ws]


def grid_problem(items: list[dict]) -> list[str]:
    """Why each grid entry can't be used (empty list = all fine), in order."""
    taken: dict[tuple[int, int], str] = {}
    problems = []
    for it in items:
        name, x, y, w, h = it["widget"], it["x"], it["y"], it["w"], it["h"]
        if name not in HOME_SIZES:
            problems.append(f"{name}: no such widget")
            continue
        ws, hs = HOME_SIZES[name]
        if w not in ws or h not in hs:
            problems.append(f"{name}: {w}x{h} isn't a size it supports ({', '.join(widget_sizes(name))})")
            continue
        if x < 0 or y < 0 or x + w > GRID_COLS or y + h > GRID_ROWS:
            problems.append(f"{name}: at {x},{y} a {w}x{h} widget runs off the {GRID_COLS}x{GRID_ROWS} grid")
            continue
        cells = [(cx, cy) for cx in range(x, x + w) for cy in range(y, y + h)]
        clash = next((taken[c] for c in cells if c in taken), None)
        if clash:
            problems.append(f"{name}: overlaps {clash}")
            continue
        for c in cells:
            taken[c] = name
    return problems


def place(items: list[tuple[str, int, int]], fixed: list[dict] | None = None) -> tuple[list[dict], list[str]]:
    """Put (widget, w, h) items in the first free spot each, row by row.
    Returns the placed entries and the names that didn't fit."""
    grid = list(fixed or [])
    left_out = []
    for name, w, h in items:
        for y in range(GRID_ROWS - h + 1):
            spot = next((x for x in range(GRID_COLS - w + 1)
                         if not grid_problem(grid + [{"widget": name, "x": x, "y": y, "w": w, "h": h}])), None)
            if spot is not None:
                grid.append({"widget": name, "x": spot, "y": y, "w": w, "h": h})
                break
        else:
            left_out.append(name)
    return grid, left_out


def columns_to_grid(left: list[str], right: list[str]) -> list[dict]:
    """Today's two columns on the grid: the left one 3 cells wide, the right one 2,
    one row per widget, with Up next taking the rest of its column."""
    grid = []
    for x, w, col in ((0, 3, left), (3, 2, right)):
        y = 0
        for i, name in enumerate(col):
            if y >= GRID_ROWS:
                break
            rest = GRID_ROWS - y
            h = rest if name == "events" and i == len(col) - 1 else 1
            h = min(h, max(HOME_SIZES[name][1]))
            if w in HOME_SIZES[name][0]:
                grid.append({"widget": name, "x": x, "y": y, "w": w, "h": h})
            y += h
    return grid


def home_grid(cfg: dict) -> list[dict]:
    """[home] grid = [{ widget = "weather", x = 0, y = 0, w = 2, h = 1 }, ...], checked;
    entries that don't fit are dropped (and logged). Without it, the columns convert."""
    home = cfg.get("home") if isinstance(cfg.get("home"), dict) else {}
    raw = home.get("grid")
    if not isinstance(raw, list):
        return columns_to_grid(*home_columns(cfg))
    good: list[dict] = []
    for e in raw:
        if not isinstance(e, dict):
            continue
        try:
            it = {"widget": str(e.get("widget", "")).lower(), "x": int(e.get("x", 0)), "y": int(e.get("y", 0)),
                  "w": int(e.get("w", 1)), "h": int(e.get("h", 1))}
        except (TypeError, ValueError):
            continue
        problem = grid_problem(good + [it])
        if problem:
            log.warning("[home] grid: %s; leaving it out", problem[-1])
        else:
            good.append(it)
    return good


def home_message(cfg: dict) -> dict:
    grid = home_grid(cfg)
    # Columns too, for board firmware from before the grid.
    left = [g["widget"] for g in sorted(grid, key=lambda g: g["y"]) if g["x"] < 3]
    right = [g["widget"] for g in sorted(grid, key=lambda g: g["y"]) if g["x"] >= 3]
    return {"type": "home", "left": left, "right": right, "header": home_header(cfg), "grid": grid}
