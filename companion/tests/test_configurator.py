"""The settings page: reading config.toml, checking edits, writing them back with
comments intact, and the HTTP API's token and host checks.

    uv run python tests/test_configurator.py
"""
import json
import pathlib
import shutil
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request

from deskhub.configurator import model
from deskhub.configurator.server import Configurator, file_version

problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)


example = (pathlib.Path(__file__).resolve().parent.parent / "config.example.toml").read_text(encoding="utf-8")
cfg = tomllib.loads(example)
state = model.read(cfg)

# ---- reading ----
check(state["pages"]["enabled"][0] == "home", "home first")
check(state["pages"]["nav"] == "left", "nav default")
check(len(state["home"]["grid"]) == 5 and state["home"]["header"] is True, f"grid read: {state['home']}")
check(len(state["tiles"]) == 8 and state["tiles"][0]["action"] == "mic", "tiles read")
check(state["display"] == {"pc_sleep": "off", "night": "", "night_style": "off"}, f"display: {state['display']}")
m = model.meta()
check({w["id"] for w in m["widgets"]} >= {"clock", "events", "github"}, "widgets in meta")
check(next(w for w in m["widgets"] if w["id"] == "events")["heights"] == [1, 2, 3], "events heights")

# ---- checks ----
check(model.problems(state) == {}, f"example config has no problems: {model.problems(state)}")
bad_grid = {"home": {"header": True, "grid": [{"widget": "media", "x": 0, "y": 0, "w": 1, "h": 1}]}}
check("home" in model.problems(bad_grid), "media can't be 1x1")
overlap = {"home": {"header": True, "grid": [{"widget": "stats", "x": 0, "y": 0, "w": 2, "h": 1},
                                             {"widget": "net", "x": 1, "y": 0, "w": 1, "h": 1}]}}
check("overlaps" in " ".join(model.problems(overlap).get("home", [])), "overlap found")
bad_tiles = {"tiles": [{"label": "X", "icon": "nope", "color": "red", "action": "keys", "target": "ctrl+nokey"},
                       {"label": "Y", "icon": "lock", "color": "#112233", "action": "run", "target": ""},
                       {"label": "Z", "icon": "lock", "color": "#112233", "action": "volume", "target": "louder"}]}
tp = " | ".join(model.problems(bad_tiles)["tiles"])
check("icon" in tp and "colour" in tp and "nokey" in tp, f"tile problems: {tp}")
check("Y:" in tp and "Z:" in tp, f"empty run and bad volume target: {tp}")
check("display" in model.problems({"display": {"pc_sleep": "off", "night": "late", "night_style": "off"}}), "bad night")
check("pages" in model.problems({"pages": {"enabled": ["home", "nope"], "nav": "left"}}), "unknown page")

# ---- writing ----
new = json.loads(json.dumps(state))
new["pages"]["enabled"] = ["home", "media", "stats"]
new["pages"]["nav"] = "bottom"
new["home"]["grid"] = [{"widget": "weather", "x": 0, "y": 0, "w": 2, "h": 1},
                       {"widget": "events", "x": 2, "y": 0, "w": 3, "h": 3}]
new["home"]["header"] = False
new["tiles"] = new["tiles"][:2] + [{"label": "Code", "icon": "code", "color": "#2F6F5E", "action": "run",
                                    "target": "code ."}]
new["display"] = {"pc_sleep": "clock", "night": "11pm-7", "night_style": "clock"}
check(model.problems(new) == {}, f"new state ok: {model.problems(new)}")
text, changed = model.apply(example, new)
check(set(changed) == {"pages", "home", "tiles", "display"}, f"changed: {changed}")
check("# Must match \"Companion token\"" in text and "# Shortcut tiles, in order." in text, "comments survive")
again = model.read(tomllib.loads(text))
check(again["pages"] == {"enabled": ["home", "media", "stats"], "nav": "bottom"}, f"pages: {again['pages']}")
check(again["home"]["header"] is False and len(again["home"]["grid"]) == 2, f"home: {again['home']}")
check(again["tiles"][2] == {"label": "Code", "icon": "code", "color": "#2f6f5e", "action": "run", "target": "code ."},
      f"tile: {again['tiles'][2]}")
check(again["tiles"][0]["target"] == "", "mic tile keeps empty target")
check(again["display"] == {"pc_sleep": "clock", "night": "23:00-07:00", "night_style": "clock"}, f"display: {again['display']}")
check(tomllib.loads(text)["hub"]["token"] == "change-me", "other sections untouched")

# Nothing changed: the file comes back byte for byte.
same, changed = model.apply(example, state)
check(same == example and changed == [], f"no-op save changes nothing: {changed}")

# Turning night mode off removes the key.
text2, _ = model.apply(text, {"display": {"pc_sleep": "clock", "night": "", "night_style": "clock"}})
check("night =" not in text2.replace("# night", ""), "night removed")

# ---- options (services) ----
svc = state["services"]
check(svc["agent"] == "auto" and svc["calendar_days"] == 7 and svc["steam"] is True and svc["presets_disabled"] == [],
      f"services read: {svc}")
s2 = dict(svc, agent="codex", speedtest_hours=1.5, calendar_days=14.0, presets_disabled=["Roblox"], hub_host="10.0.0.5")
check(model.problems({"services": s2}) == {}, f"services ok: {model.problems({'services': s2})}")
check("services" in model.problems({"services": dict(svc, presets_disabled=["Nope"])}), "unknown preset refused")
check("services" in model.problems({"services": dict(svc, calendar_days=0)}), "0 days refused")
check("services" in model.problems({"services": dict(svc, hub_host="a b")}), "bad host refused")
text3, changed = model.apply(example, {"services": s2})
again = tomllib.loads(text3)
check(changed == ["services"] and again["ai"]["agent"] == "codex" and again["internet"]["speedtest_hours"] == 1.5,
      "services written")
check(again["calendar"]["days"] == 14 and isinstance(again["calendar"]["days"], int), "whole days stay whole")
check(again["game_presets"]["disabled"] == ["Roblox"] and again["hub"]["host"] == "10.0.0.5", "presets and host")
check("github" not in again, "untouched defaults aren't written")
check(model.read(again)["services"] == s2 | {"calendar_days": 14}, "services round trip")
check(any(t["type"] == "prusalink" and t["secret_required"] for t in model.meta()["printer_types"]), "printer types")

# ---- actions that edit config.toml (no network) ----
from deskhub.configurator import actions  # noqa: E402

tmp0 = pathlib.Path(tempfile.mkdtemp())
try:
    cfgp = tmp0 / "config.toml"
    cfgp.write_text(example, encoding="utf-8")
    actions.game_add(cfgp, {"name": "Factorio", "process": "factorio.exe", "launch": "C:\\Games\\factorio.exe"})
    games = tomllib.loads(cfgp.read_text(encoding="utf-8"))["games"]
    check(games == [{"name": "Factorio", "process": "factorio.exe", "launch": "C:/Games/factorio.exe"}], f"game: {games}")
    check("games" in tomllib.loads(cfgp.read_text(encoding="utf-8"))["pages"]["enabled"], "games page on")
    try:
        actions.game_add(cfgp, {"name": "factorio", "process": "x.exe"})
        check(False, "duplicate game refused")
    except actions.ActionError:
        pass
    actions.game_remove(cfgp, {"index": 0})
    check(not tomllib.loads(cfgp.read_text(encoding="utf-8")).get("games"), "game removed")
    actions.calendar_edit(cfgp, {"index": 0, "name": "Home", "color": "#112233"})
    feed = tomllib.loads(cfgp.read_text(encoding="utf-8"))["calendar"]["feeds"][0]
    check(feed["name"] == "Home" and feed["color"] == "#112233", f"calendar edited: {feed}")
    actions.calendar_remove(cfgp, {"index": 0})
    check(tomllib.loads(cfgp.read_text(encoding="utf-8"))["calendar"]["feeds"] == [], "calendar removed")
    check("# Must match \"Companion token\"" in cfgp.read_text(encoding="utf-8"), "action keeps comments")
    try:
        actions.calendar_remove(cfgp, {"index": 0})
        check(False, "removing from an empty list refused")
    except actions.ActionError:
        pass

    # Firmware settings into a scratch firmware folder.
    fw = tmp0 / "firmware"
    fw.mkdir()
    (fw / "sdkconfig").write_text('CONFIG_HUB_WIFI_SSID="old"\nCONFIG_HUB_TOKEN="change-me"\n', encoding="utf-8")
    real_fw = actions.FIRMWARE_DIR
    actions.FIRMWARE_DIR = fw
    try:
        out = actions.board_save(cfgp, {"ssid": "Home Net", "password": "secret123", "fahrenheit": True, "h24": False,
                                        "screen_off_min": 15,
                                        "place": {"name": "Paris", "latitude": 48.85, "longitude": 2.35,
                                                  "timezone": "Europe/Paris"}})
        sdk = (fw / "sdkconfig").read_text(encoding="utf-8")
        check(out["changed"] and 'CONFIG_HUB_WIFI_SSID="Home Net"' in sdk and "CONFIG_HUB_FAHRENHEIT=y" in sdk, sdk)
        check('CONFIG_HUB_CITY="Paris"' in sdk and "CET-1CEST" in sdk and "CONFIG_HUB_SCREEN_OFF_MIN=15" in sdk, sdk)
        tok = tomllib.loads(cfgp.read_text(encoding="utf-8"))["hub"]["token"]
        check(tok != "change-me" and f'CONFIG_HUB_TOKEN="{tok}"' in sdk, "token made and shared")
        b = actions.board_read(cfgp, {})
        check(b["ssid"] == "Home Net" and b["has_password"] and b["city"] == "Paris" and b["fahrenheit"] and not b["h24"],
              f"board read: {b}")
        check("password" not in json.dumps(b).replace("has_password", ""), "password never sent back")
        for bad in ({"ssid": "x" * 33}, {"ssid": "a", "password": "short"}, {"ssid": "a", "screen_off_min": 999}):
            try:
                actions.board_save(cfgp, bad)
                check(False, f"refused: {bad}")
            except actions.ActionError:
                pass
    finally:
        actions.FIRMWARE_DIR = real_fw
finally:
    shutil.rmtree(tmp0, ignore_errors=True)

# ---- HTTP ----
tmp = pathlib.Path(tempfile.mkdtemp())
try:
    path = tmp / "config.toml"
    path.write_text(example, encoding="utf-8")
    applied = []
    app = Configurator(path, on_apply=lambda c, ch: applied.append(ch) or ["note"])
    app.start(advertise=False)
    base = f"http://127.0.0.1:{app.port}"

    def call(p, body=None, token=app.token, host=None):
        headers = {"X-Deskhub-Token": token} if token else {}
        if host:
            headers["Host"] = host
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + p, data=data, headers=headers, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    code, body = call("/")
    check(code == 200 and b"Desk Hub settings" in body, "index served")
    check(call("/app.js")[0] == 200, "js served")
    check(call("/../server.py")[0] == 404, "no path escape")
    check(call("/api/state", token="")[0] == 401, "state needs the token")
    check(call("/api/state", token="wrong")[0] == 401, "wrong token refused")
    check(call("/api/state", host="evil.example:80")[0] == 403, "foreign Host refused")
    code, body = call("/api/state")
    got = json.loads(body)
    check(code == 200 and got["state"] == state and got["live"] is True, "state over HTTP")
    v = got["version"]
    check(call("/api/save", {"version": v, "state": {"display": {"pc_sleep": "nap", "night": "", "night_style": "off"}}})[0] == 400,
          "bad save refused")
    check(path.read_text(encoding="utf-8") == example, "refused save writes nothing")
    code, body = call("/api/save", {"version": v, "state": {"pages": new["pages"]}})
    out = json.loads(body)
    check(code == 200 and out["saved"] == ["pages"] and out["applied"] and out["notes"] == ["note"], f"save: {out}")
    check(applied == [["pages"]], f"applied: {applied}")
    check(out["version"] == file_version(path.read_text(encoding="utf-8")), "new version returned")
    check(call("/api/save", {"version": v, "state": {"pages": state["pages"]}})[0] == 409, "stale version refused")
    check(call("/api/save", {"version": out["version"], "state": {}}, token="")[0] == 401, "save needs the token")
    code, body = call("/api/action", {"name": "game_add", "args": {"name": "Doom", "process": "doom.exe"}})
    out = json.loads(body)
    check(code == 200 and out["state"]["lists"]["games"][0]["name"] == "Doom" and out["restart"], f"action: {out}")
    code, body = call("/api/action", {"name": "game_add", "args": {"name": ""}})
    check(code == 400 and json.loads(body)["error"].endswith("."), f"action error: {body}")
    check(call("/api/action", {"name": "nope"})[0] == 404, "unknown action")
    check(call("/api/action", {"name": "restart"})[0] == 400, "no restart without a companion")
    check(call("/api/action", {"name": "game_add", "args": {}}, token="")[0] == 401, "actions need the token")
    app.stop()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if problems:
    print("\n".join(problems))
    sys.exit(1)
print("OK configurator")
