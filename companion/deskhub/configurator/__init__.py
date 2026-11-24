"""The settings page for config.toml.

    uv run deskhub-config [--config path/to/config.toml]

Opens the settings page of the running companion, which applies changes to the
board as they're saved. Without a running companion it serves the page itself;
changes are saved and the board gets them when the companion next starts.
"""
import argparse
import json
import logging
import pathlib
import sys
import threading
import urllib.request
import webbrowser

from .server import DISCOVERY, Configurator

__all__ = ["Configurator", "running_url", "main"]


def running_url() -> str | None:
    """The running companion's settings page, if one answers."""
    try:
        info = json.loads(DISCOVERY.read_text(encoding="utf-8"))
        port, token = int(info["port"]), str(info["token"])
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/ping", headers={"X-Deskhub-Token": token})
        with urllib.request.urlopen(req, timeout=2) as r:
            if r.status == 200:
                return f"http://127.0.0.1:{port}/#t={token}"
    except (OSError, ValueError, KeyError):
        pass
    return None


def main():
    ap = argparse.ArgumentParser(description="Desk Hub settings in your browser.")
    ap.add_argument("--config")
    ap.add_argument("--no-browser", action="store_true", help="print the address instead of opening it")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    url = None if args.config else running_url()
    app = None
    if url:
        print("Opening the companion's settings page.")
    else:
        from ..__main__ import find_config

        path = find_config(args.config)
        app = Configurator(path.resolve())
        app.start(advertise=False)
        url = app.url
        print(f"Editing {path}")
        print("The companion isn't running, so changes reach the board when it next starts.")
        print("Leave this window open while you use the page; Ctrl+C stops it.")
    if args.no_browser:
        print(url, flush=True)
    else:
        webbrowser.open(url)
    if app:
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        app.stop()
    sys.exit(0)
