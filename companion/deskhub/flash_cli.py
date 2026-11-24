"""Build the firmware and install it on the board, over Wi-Fi when it can.

    uv run deskhub-flash             # build, then send it over Wi-Fi (USB if that can't work)
    uv run deskhub-flash --usb       # build and flash over USB
    uv run deskhub-flash --no-build  # send the last build

Over Wi-Fi the board asks first: tap Install on its screen.
"""
import argparse
import os
import pathlib
import subprocess
import sys
import tomllib

import httpx

FIRMWARE_DIR = pathlib.Path(__file__).resolve().parents[2] / "firmware"
COMPANION_DIR = pathlib.Path(__file__).resolve().parents[1]

# What a Wi-Fi install can come back with.
OK, DENIED, NO_ANSWER, UNREACHABLE, NO_OTA, BAD_TOKEN, FAILED = range(7)


def run_idf(firmware: pathlib.Path, command: str) -> bool:
    """Run `idf.py <command>` in the firmware folder with ESP-IDF set up. Returns success."""
    from .setup_cli import find_idf, find_idf_python_env

    idf = find_idf()
    if not idf:
        print("ESP-IDF not found (looked in IDF_PATH, ~/esp, C:/Espressif/frameworks and C:/esp).\n"
              "Install ESP-IDF 5.5, or build and flash by hand (see the README).")
        return False
    env = find_idf_python_env(idf)
    if env:
        # Run ESP-IDF with the Python it was installed with. export.ps1 looks for a
        # python_env matching whichever `python` comes first on PATH.
        script = (f'$env:IDF_PYTHON_ENV_PATH = "{env}"; '
                  f'$env:PATH = "{env / "Scripts"};" + $env:PATH; ')
    else:
        script = f'$env:PATH = "{pathlib.Path(sys.base_prefix)};" + $env:PATH; '
    script += f'. "{idf / "export.ps1"}" | Out-Null; Set-Location "{firmware}"; idf.py {command}; exit $LASTEXITCODE'
    # ESP-IDF refuses to run when it sees an MSYS/Git Bash environment, even from PowerShell.
    env_vars = {k: v for k, v in os.environ.items() if k not in ("MSYSTEM", "MSYSTEM_PREFIX", "MINGW_PREFIX")}
    # Run from the settings page, the output goes to the page, not a console window.
    flags = subprocess.CREATE_NO_WINDOW if os.environ.get("DESKHUB_NO_WINDOW") and sys.platform == "win32" else 0
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], env=env_vars,
                       creationflags=flags)
    return r.returncode == 0


def app_image(firmware: pathlib.Path) -> pathlib.Path:
    return firmware / "build" / "deskhub.bin"


def send_over_wifi(image: pathlib.Path, host: str, token: str, post=httpx.post) -> int:
    """Upload the app image to the board's /firmware endpoint. The board asks first
    (up to a minute), then installs it and restarts."""
    try:
        r = post(f"http://{host}/firmware", params={"token": token}, content=image.read_bytes(),
                 headers={"Content-Type": "application/octet-stream"},
                 timeout=httpx.Timeout(10, read=180))
    except httpx.HTTPError:
        return UNREACHABLE
    if r.status_code == 200:
        return OK
    if r.status_code == 404:
        return NO_OTA          # firmware from before Wi-Fi updates
    if r.status_code == 403:
        return BAD_TOKEN if "token" in r.text else DENIED
    if r.status_code == 408:
        return NO_ANSWER
    return FAILED


def hub_settings(config: pathlib.Path) -> tuple[str, str]:
    cfg = tomllib.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}
    hub = cfg.get("hub", {})
    return hub.get("host", "deskhub.local"), hub.get("token", "")


def install(firmware: pathlib.Path, config: pathlib.Path, build: bool = True, usb: bool = False,
            token: str | None = None, ask_port=None) -> bool:
    """Build, then install over Wi-Fi, falling back to USB. Returns success.
    token: the token the board has now, if it differs from config.toml's."""
    if build:
        print("Building the firmware. The first build takes a few minutes.")
        if not run_idf(firmware, "build"):
            print("The build failed; see the output above. The board was NOT updated.")
            return False
    image = app_image(firmware)
    if not usb and image.is_file():
        host, cfg_token = hub_settings(config)
        print(f"Sending it to {host} over Wi-Fi. Tap Install on the board's screen.")
        result = send_over_wifi(image, host, token or cfg_token)
        if result == OK:
            print("Installed. The board restarts with the new firmware.")
            return True
        if result == DENIED:
            print("Not installed: Deny was tapped on the board.")
            return False
        if result == NO_ANSWER:
            print("Not installed: nobody tapped Install on the board within a minute. Run this again.")
            return False
        print({UNREACHABLE: f"The board isn't reachable at {host}.",
               NO_OTA: "The board's firmware is too old for Wi-Fi updates (this USB flash adds them).",
               BAD_TOKEN: "The board didn't accept the token (it changed); USB it is.",
               FAILED: "The Wi-Fi install failed."}[result] + " Trying USB instead.")
    from .setup_cli import find_port

    port = find_port() or (ask_port() if ask_port else None)
    if not port:
        print("No board found on USB (plug it in, or give its COM port with --port). NOT flashed.")
        return False
    print(f"Flashing over USB on {port}.")
    ok = run_idf(firmware, f"-p {port} flash")
    print("Done. The board restarts with the new firmware." if ok else "Flashing failed; see the output above.")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--usb", action="store_true", help="flash over USB even if Wi-Fi would work")
    ap.add_argument("--no-build", action="store_true", help="send the last build without building")
    ap.add_argument("--port", help="COM port for USB (found automatically when only one board is plugged in)")
    ap.add_argument("--config", default=str(COMPANION_DIR / "config.toml"))
    ap.add_argument("--firmware", default=str(FIRMWARE_DIR))
    ap.add_argument("--board-token", help=argparse.SUPPRESS)   # the board's token, when config.toml's is new
    args = ap.parse_args()
    ok = install(pathlib.Path(args.firmware), pathlib.Path(args.config), build=not args.no_build,
                 usb=args.usb, token=args.board_token, ask_port=(lambda: args.port) if args.port else None)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
