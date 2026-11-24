"""Desk hub companion: streams PC data to the hub and runs its commands.

    uv run python -m deskhub [--config path/to/config.toml] [--verbose]
"""
import argparse
import asyncio
import json
import logging
import os
import pathlib
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor

import websockets

from . import audio_state
from .calendar_feed import fetch_events
from .claude_alerts import ClaudeAlerts
from .claude_usage import ClaudeUsage
from .codex_usage import CodexUsage, codex_home
from .media import Media
from .netstats import NetStats
from .pages import enabled_pages, home_grid, home_message, layout_message, pc_sleep_mode
from .pc_power import PowerWatch
from .printer import PrinterService
from .shortcuts import hub_view, lit_message, load_tiles, run_tile
from .stats import Stats
from .custom_games import CustomGames, load_games
from .steam import Steam, steam_installed

log = logging.getLogger("deskhub")

CALENDAR_REFRESH_S = 600
PRINTER_TICK_S = 2
PRINTER_KEEPALIVE_S = 30
STEAM_TICK_S = 2
STEAM_KEEPALIVE_S = 60
NET_TICK_S = 2
SPEEDTEST_MIN_GAP_S = 120
GITHUB_TICK_S = 30


LOG_FILE = pathlib.Path.home() / ".deskhub" / "companion.log"
_instance_mutex = None


def single_instance() -> bool:
    """True if no other companion runs for this user (a named Windows mutex)."""
    global _instance_mutex
    if sys.platform != "win32":
        return True
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _instance_mutex = kernel32.CreateMutexW(None, False, "Local\\DeskHubCompanion")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def release_instance():
    """Let another companion start (before restarting this one)."""
    global _instance_mutex
    if _instance_mutex:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(_instance_mutex))
        _instance_mutex = None


def find_config(arg: str | None) -> pathlib.Path:
    candidates = [pathlib.Path(arg)] if arg else [
        pathlib.Path.cwd() / "config.toml",
        pathlib.Path(__file__).resolve().parent.parent / "config.toml",
    ]
    for p in candidates:
        if p.is_file():
            return p
    sys.exit("config.toml not found. Copy config.example.toml to config.toml and edit it.")


def pick_ai(agent: str, claude: dict | None, codex: dict | None) -> dict:
    """The AI page message. "auto" shows whichever agent was active last (Claude on a tie)."""
    if agent == "codex" and codex is not None:
        provider = "codex"
    elif agent == "auto" and codex is not None and claude is not None \
            and codex.get("last_active", 0) > claude.get("last_active", 0):
        provider = "codex"
    elif claude is not None:
        provider = "claude"
    else:
        provider = "codex"
    snap = codex if provider == "codex" else claude
    return {**snap, "type": "ai", "provider": provider}


def _steam_key(msg: dict) -> dict:
    """The Steam message without the session clock, which the board counts itself."""
    playing = msg.get("playing")
    return {**msg, "playing": {k: v for k, v in playing.items() if k != "session_s"} if playing else None}


class Companion:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        hub = cfg.get("hub", {})
        self.host = hub.get("host", "deskhub.local")
        self.url = f"ws://{self.host}/ws"
        self.on_status = None   # (connected, detail) -> None, e.g. the tray icon
        self.token = hub.get("token", "")
        self.stats = Stats()
        self.media = Media()
        self.servers = None     # Plex / Jellyfin: their own section on the Media page
        if cfg.get("media_servers"):
            from .media_server import MediaServers, build_servers

            servers = build_servers(cfg["media_servers"])
            if servers:
                self.servers = MediaServers(servers, cfg.get("media", {}).get("server_users"))
                log.info("media servers: %s", ", ".join(f"{s.name} ({s.url})" for s in servers))
        self.tiles = load_tiles(cfg)
        self.tiles_loop_on = False
        # Core Audio calls need COM, so they run on one dedicated thread.
        self.audio_pool = ThreadPoolExecutor(1, thread_name_prefix="audio", initializer=audio_state.com_thread)
        self.lit_msg = None
        self.events: list[dict] = []
        live = None
        if cfg.get("claude", {}).get("live_limits"):
            from .claude_live import LiveLimits
            live = LiveLimits()
            log.info("live Claude limits enabled")
        self.agent = cfg.get("ai", {}).get("agent", "auto")
        if self.agent not in ("auto", "claude", "codex"):
            log.warning("[ai] agent = %r is not auto, claude or codex; using auto", self.agent)
            self.agent = "auto"
        self.claude = ClaudeUsage(live=live) if self.agent != "codex" else None
        self.codex = CodexUsage() if self.agent == "codex" or (
            self.agent == "auto" and codex_home().is_dir()) else None
        self.claude_msg = None
        ccfg = cfg.get("claude", {})
        self.alerts = (ClaudeAlerts(idle_after=float(ccfg.get("idle_alert_seconds", 30)))
                       if ccfg.get("alerts", True) else None)
        self.printer_msg = None
        custom = CustomGames(load_games(cfg))
        use_steam = bool(cfg.get("steam", {}).get("enabled", True))
        web = None
        if use_steam:
            from .steam_web import SteamWeb, get_key

            key = get_key()  # optional, from `deskhub-setup` (Games step)
            if key:
                web = SteamWeb(key)
                log.info("Steam Web API: friends and playtime on")
        self.steam = (Steam(custom=custom, use_steam=use_steam, web=web)
                      if use_steam or custom.games else None)
        self.steam_msg = None
        icfg = cfg.get("internet", {})
        self.net = (NetStats(show_ip=bool(icfg.get("show_ip", False)))
                    if icfg.get("enabled", True) else None)
        self.net_msg = None
        self.speedtest_at = -SPEEDTEST_MIN_GAP_S
        self.github = None
        gcfg = cfg.get("github", {})
        if gcfg.get("enabled", True) and (any(g["widget"] == "github" for g in home_grid(cfg))
                                          or "github" in enabled_pages(cfg)):
            from .github import GitHub, get_token

            token = get_token()  # from `deskhub-setup github`
            if token:
                self.github = GitHub(token, accent=str(gcfg.get("colors", "green")).lower() == "accent")
            else:
                log.info("the GitHub widget or page is on but no token is saved; run: uv run deskhub-setup github")
        self.connected_once = False
        self.ws = None
        self.loop = None
        self.pc_asleep = False
        self.power = PowerWatch(self.on_pc_power) if pc_sleep_mode(cfg) != "none" else None

    def on_pc_power(self, asleep: bool):
        """From the power-watch thread: tell the board the PC's display slept or woke."""
        self.pc_asleep = asleep
        if self.loop is None:
            return
        fut = asyncio.run_coroutine_threadsafe(self.send({"type": "pc_power", "asleep": asleep}), self.loop)
        try:
            # Before a suspend the network goes down soon after this returns.
            fut.result(timeout=2)
        except Exception:
            pass

    def status(self, connected: bool, detail: str):
        if self.on_status:
            try:
                self.on_status(connected, detail)
            except Exception as e:
                log.debug("status callback failed: %s", e)

    async def send(self, msg: dict | bytes):
        ws = self.ws
        if ws is None:
            return
        try:
            await ws.send(msg if isinstance(msg, bytes) else json.dumps(msg, separators=(",", ":")))
        except websockets.ConnectionClosed:
            pass

    # ---- producers --------------------------------------------------------

    async def stats_loop(self):
        while True:
            await self.send(self.stats.sample())
            await asyncio.sleep(1)

    async def media_loop(self):
        await self.media.start()
        while True:
            try:
                msg, art = await self.media.snapshot()
                if art:
                    await self.send(art)
                await self.send(msg)
            except Exception as e:
                log.debug("media poll failed: %s", e)
            await asyncio.sleep(1)

    async def media_server_send_loop(self):
        """The server section, once a second (the cover first, so the message names it)."""
        while True:
            try:
                art = await asyncio.to_thread(self.servers.art)
                if art:
                    await self.send(art)
                await self.send(self.servers.message())
            except Exception as e:
                log.debug("media server message failed: %s", e)
            await asyncio.sleep(1)

    async def media_server_loop(self):
        while True:
            try:
                await asyncio.to_thread(self.servers.poll)
            except Exception as e:
                log.warning("media server poll failed: %s", e)
            await asyncio.sleep(self.servers.interval())

    def ai_snapshot(self) -> dict:
        claude = self.claude.snapshot() if self.claude else None
        codex = self.codex.snapshot() if self.codex else None
        return pick_ai(self.agent, claude, codex)

    async def tiles_loop(self):
        """Light up toggle tiles (mic and speaker mute) to match Windows."""
        while True:
            await self.refresh_lit()
            await asyncio.sleep(1)

    async def refresh_lit(self):
        try:
            states = await asyncio.get_running_loop().run_in_executor(self.audio_pool, audio_state.read_states)
        except Exception as e:
            log.warning("tile states failed: %s", e)
            return
        msg = lit_message(self.tiles, states)
        if msg != self.lit_msg:
            self.lit_msg = msg
            await self.send(msg)

    async def claude_loop(self):
        while True:
            try:
                self.claude_msg = await asyncio.to_thread(self.ai_snapshot)
                await self.send(self.claude_msg)
            except Exception as e:
                log.warning("AI usage failed: %s", e)
            await asyncio.sleep(5)

    async def alerts_loop(self):
        while True:
            try:
                msg = await asyncio.to_thread(self.alerts.poll)
                if msg:
                    await self.send(msg)
            except Exception as e:
                log.warning("claude alerts failed: %s", e)
            await asyncio.sleep(1)

    def events_message(self) -> dict:
        # "days" lets the hub say how far ahead it looked ("No more events in the next 7 days").
        days = int(self.cfg.get("calendar", {}).get("days", 7))
        return {"type": "events", "events": self.events, "days": days}

    async def calendar_loop(self):
        cal = self.cfg.get("calendar", {})
        feeds, days = cal.get("feeds", []), int(cal.get("days", 7))
        while True:
            self.events = await fetch_events(feeds, days)
            log.info("calendar: %d upcoming events", len(self.events))
            await self.send(self.events_message())
            await asyncio.sleep(CALENDAR_REFRESH_S)

    async def printer_loop(self):
        service = PrinterService(self.cfg.get("printers", []))
        if not service.workers:
            return
        service.start()
        sent_at = 0.0
        try:
            while True:
                msg = service.message()
                now = asyncio.get_running_loop().time()
                # Send on change (checked every 2 s) and at least every 30 s.
                if msg != self.printer_msg or now - sent_at >= PRINTER_KEEPALIVE_S:
                    self.printer_msg = msg
                    sent_at = now
                    await self.send(msg)
                await asyncio.sleep(PRINTER_TICK_S)
        finally:
            service.stop()  # lets each printer connection close cleanly on exit

    async def steam_loop(self):
        if not (self.steam.use_steam and steam_installed()) and not self.steam.custom.games:
            return
        sent_at = 0.0
        last = None
        while True:
            try:
                msg = await asyncio.to_thread(self.steam.snapshot)
                self.steam_msg = msg
                key = _steam_key(msg)
                now = asyncio.get_running_loop().time()
                if key != last or now - sent_at >= STEAM_KEEPALIVE_S:
                    last, sent_at = key, now
                    await self.send(msg)
                for frame in await asyncio.to_thread(self.steam.frames):
                    await self.send(frame)
            except Exception as e:
                log.warning("steam poll failed: %s", e)
            await asyncio.sleep(STEAM_TICK_S)

    async def net_loop(self):
        while True:
            try:
                await asyncio.to_thread(self.net.tick)
                self.net_msg = self.net.message()
                await self.send(self.net_msg)
            except Exception as e:
                log.warning("net stats failed: %s", e)
            await asyncio.sleep(NET_TICK_S)

    async def github_loop(self):
        while True:
            try:
                msg = await asyncio.to_thread(self.github.poll)
                if msg:
                    await self.send(msg)
            except Exception as e:
                log.warning("github poll failed: %s", e)
            await asyncio.sleep(GITHUB_TICK_S)

    async def speedtest(self):
        """Run a speed test now (at most one at a time, one per two minutes)."""
        now = time.monotonic()
        if not self.net or self.net.testing or now - self.speedtest_at < SPEEDTEST_MIN_GAP_S:
            return
        self.speedtest_at = now
        task = asyncio.create_task(asyncio.to_thread(self.net.run_speedtest))
        await asyncio.sleep(0)  # let the thread flag testing = True
        while not self.net.testing and not task.done():
            await asyncio.sleep(0.05)
        self.net_msg = self.net.message()
        await self.send(self.net_msg)
        await task
        self.net_msg = self.net.message()
        await self.send(self.net_msg)

    async def speedtest_schedule(self, hours: float):
        while True:
            await asyncio.sleep(hours * 3600)
            await self.speedtest()

    # ---- settings page ----------------------------------------------------

    async def reload(self, cfg: dict, changed: list[str]) -> list[str]:
        """Take new settings from the settings page: pages, Home, tiles and the screen
        go to the board now. Returns notes on what still needs a restart."""
        old = self.cfg
        self.cfg = cfg
        notes = []
        if "tiles" in changed:
            self.tiles = load_tiles(cfg)
            self.lit_msg = None
            await self.send(hub_view(self.tiles))
            if any(t["state"] for t in self.tiles):
                if self.tiles_loop_on:
                    await self.refresh_lit()
                else:
                    notes.append("Restart the companion for tiles that light up to follow Windows.")
        if "pages" in changed or "display" in changed:
            await self.send(layout_message(cfg))
        if "home" in changed or "pages" in changed:
            await self.send(home_message(cfg))
        if "pages" in changed:
            # Pages whose data comes from loops started at launch.
            added = set(enabled_pages(cfg)) - set(enabled_pages(old))
            needs = sorted(added & {"printer", "games", "github"})
            if needs:
                from .pages import PAGE_LABELS

                names = " and ".join(PAGE_LABELS[p] for p in needs)
                notes.append(f"Restart the companion so {names} gets its data.")
        if "display" in changed and (pc_sleep_mode(cfg) == "none") != (pc_sleep_mode(old) == "none"):
            notes.append("Restart the companion for the new PC sleep setting.")
        return notes

    def reload_threadsafe(self, cfg: dict, changed: list[str]) -> list[str]:
        if self.loop is None:
            self.cfg = cfg
            return []
        return asyncio.run_coroutine_threadsafe(self.reload(cfg, changed), self.loop).result(timeout=10)

    # ---- hub commands -----------------------------------------------------

    async def handle(self, raw):
        if isinstance(raw, bytes):
            return
        msg = json.loads(raw)
        kind = msg.get("type")
        if kind == "media":
            await self.media.command(msg.get("cmd", ""), int(msg.get("value", 0)))
        elif kind == "media_server" and self.servers:
            await asyncio.to_thread(self.servers.command, msg.get("cmd", ""), int(msg.get("value", 0)))
        elif kind == "alert_action" and self.alerts:
            sid, action = str(msg.get("id", "")), msg.get("action")
            if action == "dismiss":
                self.alerts.dismiss(sid)
            elif action == "focus":
                await asyncio.to_thread(self.alerts.focus, sid)
        elif kind == "speedtest" and self.net:
            asyncio.create_task(self.speedtest())
        elif kind == "steam_launch" and self.steam:
            await asyncio.to_thread(self.steam.launch, int(msg.get("appid", 0)))
        elif kind == "shortcut":
            i = int(msg.get("id", -1))
            if 0 <= i < len(self.tiles):
                try:
                    if self.tiles[i]["action"] == "mic":
                        log.info("shortcut %r: mic", self.tiles[i]["label"])
                        await asyncio.get_running_loop().run_in_executor(self.audio_pool, audio_state.toggle_mic)
                        await self.refresh_lit()
                        return
                    pending = run_tile(self.tiles[i], self.media)
                    if pending is not None:
                        await pending
                except Exception as e:
                    log.warning("shortcut %d failed: %s", i, e)

    async def session(self):
        async with websockets.connect(self.url, max_size=2**20, ping_interval=10,
                                      ping_timeout=10, open_timeout=10) as ws:
            await ws.send(json.dumps({"type": "hello", "token": self.token}))
            reply = json.loads(await asyncio.wait_for(ws.recv(), 10))
            if reply.get("type") != "hello_ok":
                raise RuntimeError(f"hub refused hello: {reply}")
            log.info("connected to hub (firmware %s)", reply.get("version", "?"))
            self.connected_once = True
            peer = ws.remote_address[0] if ws.remote_address else ""
            self.status(True, f"connected to {self.host}" + (f" ({peer})" if peer else ""))
            self.ws = ws
            # Everything the hub keeps in RAM, resent after each (re)connect.
            await self.send(layout_message(self.cfg))
            await self.send({"type": "pc_power", "asleep": self.pc_asleep})
            await self.send(home_message(self.cfg))
            await self.send(hub_view(self.tiles))
            if self.lit_msg:
                await self.send(self.lit_msg)
            await self.send(self.events_message())
            if self.claude_msg:
                await self.send(self.claude_msg)
            if self.alerts and self.alerts.msg:
                await self.send(self.alerts.msg)
            if self.printer_msg:
                await self.send(self.printer_msg)
            if self.net_msg:
                await self.send(self.net_msg)
            if self.github and self.github.msg:
                await self.send(self.github.msg)
            if self.steam_msg and self.steam:
                await self.send(self.steam_msg)
                for frame in await asyncio.to_thread(self.steam.all_frames):
                    await self.send(frame)
            if self.servers:
                if self.servers.current_art():
                    await self.send(self.servers.current_art())
                await self.send(self.servers.message())
            else:
                await self.send({"type": "media_server", "configured": False})
            art = self.media.current_art()
            if art:
                await self.send(art)
            async for raw in ws:
                try:
                    await self.handle(raw)
                except Exception as e:
                    log.warning("bad message from hub: %s", e)

    async def run(self):
        self.loop = asyncio.get_running_loop()
        if self.power:
            self.power.start()
        asyncio.create_task(self.stats_loop())
        asyncio.create_task(self.media_loop())
        if self.servers:
            asyncio.create_task(self.media_server_loop())
            asyncio.create_task(self.media_server_send_loop())
        asyncio.create_task(self.calendar_loop())
        asyncio.create_task(self.claude_loop())
        if any(t["state"] for t in self.tiles):
            self.tiles_loop_on = True
            asyncio.create_task(self.tiles_loop())
        if self.alerts:
            asyncio.create_task(self.alerts_loop())
        if "printer" in enabled_pages(self.cfg):
            asyncio.create_task(self.printer_loop())
        if self.steam:
            asyncio.create_task(self.steam_loop())
        if self.github:
            asyncio.create_task(self.github_loop())
        if self.net:
            asyncio.create_task(self.net_loop())
            hours = float(self.cfg.get("internet", {}).get("speedtest_hours", 0))
            if hours > 0:
                asyncio.create_task(self.speedtest_schedule(hours))
        delay = 2
        while True:
            try:
                await self.session()
                delay = 2
            except (OSError, asyncio.TimeoutError, websockets.WebSocketException, RuntimeError) as e:
                log.info("hub not reachable at %s (%s), retrying in %ds", self.url, e, delay)
            finally:
                self.ws = None
                self.status(False, f"looking for {self.host}")
            # A link that came up and later dropped (e.g. the hub rebooted) retries fast.
            if self.connected_once:
                self.connected_once = False
                delay = 2
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--log", help=f"log to this file (default when started hidden: {LOG_FILE})")
    ap.add_argument("--tray", action="store_true", help="show an icon in the notification area")
    args = ap.parse_args()
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    level = logging.DEBUG if args.verbose else logging.INFO
    # Started hidden (pythonw, e.g. from the login shortcut) there's no console to log to.
    log_file = pathlib.Path(args.log) if args.log else LOG_FILE if sys.stderr is None else None
    if log_file:
        from logging.handlers import RotatingFileHandler

        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=1, encoding="utf-8")
        logging.basicConfig(level=level, format=fmt, handlers=[handler])
    else:
        logging.basicConfig(level=level, format=fmt)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not single_instance():
        # Two companions would keep knocking each other off the board.
        log.error("the companion is already running (maybe started with Windows); not starting another")
        sys.exit("The Desk Hub companion is already running. Stop that one first.")
    path = find_config(args.config)
    cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    log.info("using %s", path)
    companion = Companion(cfg)
    settings = None

    def restart():
        # A fresh process re-reads config.toml and rebuilds everything cleanly.
        log.info("restarting")
        release_instance()
        if settings:
            settings.carry_over()
        subprocess.Popen([sys.executable, "-m", "deskhub", *sys.argv[1:]], cwd=os.getcwd())
        os._exit(0)

    try:
        from .configurator import Configurator

        # The settings page (tray > Settings, or `deskhub-config`), on 127.0.0.1 only.
        # It can restart the companion when it runs hidden or with the tray icon, not in a terminal.
        settings = Configurator(path.resolve(), on_apply=companion.reload_threadsafe,
                                on_restart=restart if args.tray or sys.stderr is None else None)
        settings.start()
    except Exception as e:
        log.warning("settings page unavailable: %s", e)
    if args.tray:
        from .tray import Tray

        def quit_():
            log.info("quit from the tray")
            os._exit(0)

        def open_settings():
            import webbrowser

            if settings:
                webbrowser.open(settings.url)
            else:
                os.startfile(path.resolve())

        tray = Tray(path.resolve(), log_file, restart, quit_, on_settings=open_settings)
        if tray.start():
            companion.on_status = tray.set_status
    try:
        asyncio.run(companion.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
