"use strict";
// The settings that go through actions (credentials, connection tests, firmware)
// and the Options section. Uses the helpers in app.js (h, icon, update, render...).

// Form fields typed on these pages but not saved yet, so a re-render keeps them.
const ui = { cal: { kind: "link", name: "", url: "", color: "#2dd4bf", user: "", password: "", found: null, picked: [] },
             printer: { type: "", host: "", port: "", fields: {}, secret: "", name: "", model: "", failed: "" },
             game: { name: "", title: "", process: "", launch: "", image: "", windows: null },
             keys: { steam: "", github: "" }, status: null,
             board: null, place: null, places: null, cityQuery: "", flash: null, flashPort: "", flashUsb: false,
             editCal: -1 };
let busy = false;

async function act(name, args, quiet) {
  // One button press at a time; background reads (quiet) don't wait for it.
  if (busy && !quiet) return null;
  if (!quiet) busy = true;
  document.body.style.cursor = "progress";
  try {
    const { status, data } = await api("/api/action", { name, args: args || {} });
    if (status !== 200) {
      toast(data.error || `That didn't work (error ${status}).`, true);
      return null;
    }
    if (data.state) applyServerState(data);
    if (data.restart) needRestart = true;
    if (data.message && !quiet) toast(data.message);
    return data;
  } catch {
    toast("Can't reach the companion. Is it still running?", true);
    return null;
  } finally {
    if (!quiet) busy = false;
    document.body.style.cursor = "";
  }
}

// config.toml changed on the server: take its copy, keeping unsaved edits.
function applyServerState(data) {
  const dirty = dirtySections();
  orig = data.state;
  for (const s of Object.keys(orig)) if (!dirty.includes(s)) cur[s] = clone(orig[s]);
  cur.lists = clone(orig.lists);
  version = data.version;
}

const field = (label, input, hint) => h("label", { class: "field" }, h("span", {}, label), input, hint ? h("span", { class: "hint" }, hint) : null);
const textInput = (obj, key, attrs) => h("input", { type: "text", value: obj[key] ?? "", spellcheck: "false", autocomplete: "off",
                                                   oninput: (e) => { obj[key] = e.target.value; }, ...(attrs || {}) });
const secretInput = (obj, key, attrs) => textInput(obj, key, { type: "password", autocomplete: "new-password", ...(attrs || {}) });
const svc = () => cur.services;
const setSvc = (k, v) => update(() => { cur.services[k] = v; });
const check = (label, key) => h("label", { class: "toggle" },
  h("input", { type: "checkbox", checked: svc()[key], onchange: (e) => setSvc(key, e.target.checked) }), label);
const number = (key, min, max, step) => h("input", { type: "number", min, max, step: step || 1, value: svc()[key], class: "num",
  onchange: (e) => setSvc(key, e.target.value === "" ? NaN : Number(e.target.value)) });

function restartBar() {
  if (!needRestart) return null;
  return h("div", { class: "notice" },
    h("p", {}, "Some changes take effect when the companion restarts."),
    canRestart ? h("button", { type: "button", class: "primary", onclick: restartCompanion }, "Restart the companion")
      : h("p", { class: "hint" }, live ? "Restart it from the tray icon." : "Start the companion to use them."));
}

async function restartCompanion() {
  if (dirtySections().length && !confirm("Restart without saving your other changes?")) return;
  const r = await act("restart");
  if (!r) return;
  needRestart = false;
  render();
  // The new companion takes over this page's address; wait for it.
  for (let i = 0; i < 40; i++) {
    await new Promise((res) => setTimeout(res, 1000));
    try {
      if ((await api("/api/ping")).status === 200) { await load(); toast("The companion restarted."); return; }
    } catch { /* not back yet */ }
  }
  toast("The companion hasn't come back. Check the tray icon.", true);
}

function colorPick(obj, key) {
  return h("input", { type: "color", value: obj[key], "aria-label": "Colour", oninput: (e) => { obj[key] = e.target.value; } });
}

// ---- Wi-Fi, city and units (firmware) ----------------------------------------------

async function loadBoard() {
  const r = await act("board_read", {}, true);
  if (r) { ui.board = r; ui.cityQuery = r.city; render(); }
}

function renderBoard() {
  const head = [h("h2", {}, "Wi-Fi, city and units"),
    h("p", { class: "lead" }, "These live in the board's firmware, so they reach it with a new build: save them, then Build and flash.")];
  if (!ui.board) { loadBoard(); return [...head, h("p", { class: "loading" }, "Reading the firmware settings…")]; }
  const b = ui.board;
  if (!b.available) return [...head, h("p", { class: "error" }, "The firmware folder isn't next to the companion, so these can't be changed here.")];
  const places = ui.places ? h("div", { class: "choices" }, ui.places.map((p) =>
    h("button", { type: "button", "aria-pressed": String(ui.place?.label === p.label),
                  onclick: () => { ui.place = p; ui.places = null; ui.cityQuery = p.name; render(); } }, p.label))) : null;
  const flash = ui.flash;
  const done = flash && !flash.running && flash.ok != null;
  return [...head,
    h("section", { class: "panel fw" },
      h("h3", {}, "Wi-Fi", h("span", { class: "hint" }, "2.4 GHz networks only")),
      h("div", { class: "form-row" },
        field("Network name", textInput(b, "ssid", { maxlength: "32" })),
        field("Password", secretInput(b, "password", { placeholder: b.has_password ? "Saved; type to change" : "" }))),
      h("h3", {}, "City", h("span", { class: "hint" }, "for the weather and the time zone")),
      h("div", { class: "form-row end" },
        field("Search", textInput(ui, "cityQuery", { placeholder: "Charlotte, NC or Paris, France",
          onkeydown: (e) => { if (e.key === "Enter") { e.preventDefault(); findCity(); } } })),
        h("button", { type: "button", onclick: findCity }, "Find")),
      places,
      h("p", { class: "hint" }, ui.place ? `Picked ${ui.place.label} (${ui.place.timezone}). Save to keep it.`
        : b.city ? `Now: ${b.city}.` : "None set yet."),
      h("h3", {}, "Units and clock"),
      h("label", { class: "toggle" }, h("input", { type: "checkbox", checked: b.fahrenheit, onchange: (e) => { b.fahrenheit = e.target.checked; } }),
        "Fahrenheit and mph"),
      h("label", { class: "toggle" }, h("input", { type: "checkbox", checked: b.h24, onchange: (e) => { b.h24 = e.target.checked; } }),
        "24-hour clock"),
      h("h3", {}, "Screen timeout"),
      h("label", { class: "inline" }, "Turn the screen off after",
        h("input", { type: "number", min: 0, max: 240, value: b.screen_off_min, class: "num",
                     oninput: (e) => { b.screen_off_min = Number(e.target.value); } }),
        "idle minutes", h("span", { class: "hint" }, "0 keeps it on")),
      h("div", { class: "panel-foot" },
        h("button", { type: "button", class: "primary", onclick: saveBoard }, "Save firmware settings"))),

    h("section", { class: "panel fw" },
      h("h3", {}, "Build and flash"),
      h("p", { class: "hint" }, "Builds the firmware with ESP-IDF and sends it to the board over Wi-Fi, then you tap Install on the board's screen. " +
        "When Wi-Fi can't reach it, it flashes over USB instead. The first build takes a few minutes."),
      h("details", { open: !!ui.flashOpen, ontoggle: (e) => { ui.flashOpen = e.target.open; } },
        h("summary", {}, "USB options"),
        h("div", { class: "form-row end" },
          field("COM port", textInput(ui, "flashPort", { placeholder: "COM5", class: "short" })),
          h("label", { class: "toggle tall" }, h("input", { type: "checkbox", checked: ui.flashUsb, onchange: (e) => { ui.flashUsb = e.target.checked; } }),
            "Use USB even when Wi-Fi works")),
        h("p", { class: "hint" }, "Leave the port empty to find the plugged-in board by itself.")),
      flash ? h("pre", { class: "log", id: "flashlog" }, flash.lines.join("\n") || "Starting…") : null,
      h("div", { class: "panel-foot" },
        done ? h("p", { class: flash.ok ? "ok" : "error" },
          flash.ok ? "Done. The board restarts with the new firmware." : "It didn't finish; the log above says why.") : null,
        h("button", { type: "button", class: "primary", disabled: flash?.running, onclick: startFlash },
          flash?.running ? "Building…" : done ? "Build and flash again" : "Build and flash"))),
  ];
}

async function findCity() {
  if (!ui.cityQuery.trim()) return;
  const r = await act("geocode", { query: ui.cityQuery }, true);
  if (!r) return;
  ui.places = r.places;
  if (!r.places.length) toast("No match. Add the state or country after a comma.", true);
  render();
}

async function saveBoard() {
  const b = ui.board;
  const r = await act("board_save", { ssid: b.ssid, password: b.password || "", place: ui.place, fahrenheit: b.fahrenheit,
                                      h24: b.h24, screen_off_min: b.screen_off_min });
  if (r?.changed) { ui.place = null; b.password = ""; ui.board = null; render(); }
}

async function startFlash() {
  const r = await act("flash_start", { port: ui.flashPort.trim(), usb: ui.flashUsb }, true);
  if (!r) return;
  ui.flash = r;
  render();
  while (ui.flash.running) {
    await new Promise((res) => setTimeout(res, 1000));
    try {
      const { status, data } = await api("/api/action", { name: "flash_status", args: {} });
      if (status === 200) ui.flash = data;
    } catch { break; }
    if (section === "board") {
      render();
      const log = document.getElementById("flashlog");
      if (log) log.scrollTop = log.scrollHeight;
    }
  }
}

// ---- calendars ----------------------------------------------------------------------

function renderCalendars() {
  const cals = cur.lists.calendars;
  const c = ui.cal;
  const list = h("ul", { class: "item-list" }, cals.length ? cals.map((cal, i) => ui.editCal === i
    ? h("li", {},
      h("input", { type: "color", value: cal.color, "aria-label": "Colour", oninput: (e) => { cal.color = e.target.value; } }),
      h("input", { type: "text", value: cal.name, "aria-label": "Name", oninput: (e) => { cal.name = e.target.value; } }),
      h("span", { class: "spacer" }),
      h("button", { type: "button", class: "primary", onclick: async () => {
        if (await act("calendar_edit", { index: i, name: cal.name, color: cal.color })) { ui.editCal = -1; render(); }
      } }, "Done"),
      h("button", { type: "button", class: "quiet", onclick: () => { ui.editCal = -1; cur.lists = clone(orig.lists); render(); } }, "Cancel"))
    : h("li", {},
      h("span", { class: "swatch", style: { background: cal.color } }),
      h("span", {}, h("strong", {}, cal.name || "(no name)"), h("span", { class: "hint" }, " " + cal.where)),
      h("span", { class: "spacer" }),
      h("button", { type: "button", class: "quiet", onclick: () => { ui.editCal = i; render(); } }, "Edit"),
      h("button", { type: "button", class: "quiet", onclick: async () => {
        if (confirm(`Remove ${cal.name}?` + (cal.kind === "caldav" ? " Its saved password goes too, unless another calendar uses it." : "")))
          { await act("calendar_remove", { index: i }); render(); }
      } }, "Remove")))
    : [h("li", { class: "hint" }, "No calendars yet.")]);

  const kinds = { link: "Google, Outlook or another link", apple: "Apple iCloud" };
  let form;
  if (c.kind === "link") {
    form = [
      h("p", { class: "hint" }, "Google: Settings > your calendar > Integrate calendar > Secret address in iCal format. " +
        "Outlook: Settings > Calendar > Shared calendars > Publish a calendar > ICS link. Anything with a webcal:// or .ics link works."),
      field("Address", textInput(c, "url", { placeholder: "https://… or webcal://…" })),
      h("div", { class: "form-row" }, field("Name", textInput(c, "name", { placeholder: "Personal" })), field("Colour", colorPick(c, "color"))),
      h("div", { class: "actions-row" }, h("button", { type: "button", class: "primary", onclick: async () => {
        if (await act("calendar_add_link", { url: c.url, name: c.name, color: c.color })) { c.url = ""; c.name = ""; render(); }
      } }, "Check and add")),
    ];
  } else {
    form = [
      h("p", { class: "hint" }, "Apple needs an app-specific password: account.apple.com > Sign-In and Security > App-Specific Passwords. " +
        "It goes in the Windows credential store, not config.toml."),
      h("div", { class: "form-row" }, field("Apple ID email", textInput(c, "user")), field("App-specific password", secretInput(c, "password"))),
      c.found ? h("div", { class: "field" }, h("span", { class: "hint" }, "Calendars to show"),
        h("div", { class: "checks" }, c.found.map((name) => h("label", { class: "toggle" },
          h("input", { type: "checkbox", checked: c.picked.includes(name),
                       onchange: (e) => { c.picked = e.target.checked ? [...c.picked, name] : c.picked.filter((x) => x !== name); } }), name)))) : null,
      c.found ? field("Colour", colorPick(c, "color")) : null,
      h("div", { class: "actions-row" }, c.found
        ? h("button", { type: "button", class: "primary", onclick: async () => {
          if (await act("calendar_apple_add", { username: c.user, password: c.password, calendars: c.picked, color: c.color }))
            { Object.assign(c, { user: "", password: "", found: null, picked: [] }); render(); }
        } }, "Add iCloud")
        : h("button", { type: "button", class: "primary", onclick: async () => {
          const r = await act("calendar_apple_list", { username: c.user, password: c.password }, true);
          if (r) { c.found = r.calendars; c.picked = [...r.calendars]; if (c.color === "#2dd4bf") c.color = "#ff5a5f"; render(); }
        } }, "Connect")),
    ];
  }
  return [
    h("h2", {}, "Calendars"),
    h("p", { class: "lead" }, "Events from these show on the Calendar page and in Up next on Home."),
    list,
    h("div", { class: "form-row", style: { marginTop: "14px" } },
      field("Show events for how many days ahead", number("calendar_days", 1, 60))),
    problemList("services"),
    h("h3", {}, "Add a calendar"),
    h("div", { class: "radios" }, Object.entries(kinds).map(([k, label]) => h("label", {},
      h("input", { type: "radio", name: "calkind", checked: c.kind === k, onchange: () => { c.kind = k; render(); } }), label))),
    h("div", { class: "panel" }, form),
  ];
}

// ---- printers -----------------------------------------------------------------------

function renderPrinters() {
  const ps = cur.lists.printers;
  const p = ui.printer;
  const types = meta.printer_types;
  const spec = types.find((t) => t.type === p.type);
  const list = h("ul", { class: "item-list" }, ps.length ? ps.map((pr, i) => h("li", {},
    icon("view_in_ar"), h("span", {}, pr.where), h("span", { class: "spacer" }),
    h("button", { type: "button", class: "quiet", onclick: async () => {
      if (confirm(`Remove ${pr.name}? Its saved password or access code goes too.`)) { await act("printer_remove", { index: i }); render(); }
    } }, "Remove"))) : [h("li", { class: "hint" }, "No printers yet.")]);
  let form = null;
  if (spec?.terminal) {
    form = [h("p", { class: "hint" }, spec.intro),
      h("div", { class: "actions-row" }, h("button", { type: "button", class: "primary",
        onclick: () => act("open_terminal", { tool: "printers-cloud" }) }, "Open the sign-in window"))];
  } else if (spec) {
    const add = async (force) => {
      const r = await act("printer_add", { type: p.type, host: p.host, port: p.port, fields: p.fields, secret: p.secret,
                                           name: p.name, model: p.model, force }, true);
      if (!r) return;
      if (r.ok === false) { p.failed = r.message; render(); return; }
      toast(r.message);
      Object.assign(p, { host: "", port: "", fields: {}, secret: "", name: "", model: "", failed: "" });
      render();
    };
    form = [
      h("p", { class: "hint pre" }, spec.intro),
      h("div", { class: "form-row" },
        field("IP address or host name", textInput(p, "host", { placeholder: "192.168.1.60" })),
        spec.ask_port ? field("Port", textInput(p, "port", { placeholder: String(spec.default_port), class: "short" })) : null),
      spec.fields.length ? h("div", { class: "form-row" }, spec.fields.map((f) => {
        if (!(f.key in p.fields)) p.fields[f.key] = f.default;
        return field(f.prompt + (f.required ? "" : " (optional)"), textInput(p.fields, f.key));
      })) : null,
      spec.secret_prompt ? h("div", { class: "form-row" }, field(spec.secret_prompt + (spec.secret_required ? "" : " (optional)"),
        secretInput(p, "secret"), "Kept in the Windows credential store.")) : null,
      h("div", { class: "form-row" }, field("Name (optional)", textInput(p, "name")),
        spec.type !== "local" ? field("Model shown on the board (optional)", textInput(p, "model")) : null),
      p.failed ? h("p", { class: "error" }, p.failed) : null,
      h("div", { class: "actions-row" },
        h("button", { type: "button", class: "primary", onclick: () => add(false) }, "Test and add"),
        p.failed ? h("button", { type: "button", onclick: () => add(true) }, "Add anyway") : null),
    ];
  }
  return [
    h("h2", {}, "3D printers"),
    h("p", { class: "lead" }, "Up to 4 printers in any mix. Passwords, API keys and access codes go in the Windows credential store."),
    list,
    h("h3", {}, "Add a printer"),
    field("Brand", h("select", { onchange: (e) => { Object.assign(p, { type: e.target.value, fields: {}, failed: "" }); render(); } },
      h("option", { value: "", selected: !p.type }, "Pick one"),
      types.map((t) => h("option", { value: t.type, selected: t.type === p.type }, t.menu)))),
    form ? h("div", { class: "panel" }, form) : null,
  ];
}

// ---- games --------------------------------------------------------------------------

function renderGames() {
  const games = cur.lists.games;
  const g = ui.game;
  const s = svc();
  const list = h("ul", { class: "item-list" }, games.length ? games.map((gm, i) => h("li", {},
    icon("sports_esports"), h("span", {}, h("strong", {}, gm.name), h("span", { class: "hint" }, " " + gm.where)),
    h("span", { class: "spacer" }),
    h("button", { type: "button", class: "quiet", onclick: async () => {
      if (confirm(`Remove ${gm.name}?`)) { await act("game_remove", { index: i }); render(); }
    } }, "Remove"))) : [h("li", { class: "hint" }, "None yet.")]);
  const wins = g.windows ? h("div", { class: "choices" }, g.windows.length ? g.windows.map((w) =>
    h("button", { type: "button", title: w.exe, onclick: () => {
      const sg = w.suggest;
      Object.assign(g, { name: sg.name, title: sg.title || "", process: [].concat(sg.process || []).join(", "),
                         launch: sg.launch || "", windows: null });
      render();
    } }, `${w.title.slice(0, 60)}  (${w.process})`)) : [h("p", { class: "hint" }, "No windows open.")]) : null;
  return [
    h("h2", {}, "Games"),
    h("h3", {}, "Steam"),
    check("Show Steam games: what you're playing and your recent games", "steam"),
    s.steam ? keyRow("Steam Web API key", "steam", "Adds friends in game and total playtime. Get one at steamcommunity.com/dev/apikey.",
                     "steam_key", "steam_key_set", "steam_key_remove", "key") : null,
    h("h3", {}, "Built-in games"),
    check("Recognise popular games that aren't on Steam (League of Legends, VALORANT, Fortnite, Minecraft…)", "presets"),
    s.presets ? h("details", {}, h("summary", {}, `Leave some out (${s.presets_disabled.length} left out)`),
      h("div", { class: "checks" }, meta.presets.map((name) => h("label", { class: "toggle" },
        h("input", { type: "checkbox", checked: !s.presets_disabled.includes(name),
                     onchange: (e) => setSvc("presets_disabled", e.target.checked ? s.presets_disabled.filter((x) => x !== name)
                                                                              : [...s.presets_disabled, name]) }), name)))) : null,
    problemList("services"),
    h("h3", {}, "Your own games"),
    h("p", { class: "hint" }, "Emulators, modpacks, games from other launchers. Start the game, then pick its window."),
    list,
    h("div", { class: "panel" },
      h("div", { class: "actions-row" }, h("button", { type: "button", onclick: async () => {
        const r = await act("windows", {}, true);
        if (r) { g.windows = r.windows; render(); }
      } }, "Pick from open windows")),
      wins,
      h("div", { class: "form-row" }, field("Name on the board", textInput(g, "name")),
        field("Window title contains (optional)", textInput(g, "title"))),
      field("Program file names, comma separated (Task Manager > Details)", textInput(g, "process", { placeholder: "javaw.exe" })),
      field("What tapping it opens (optional)", textInput(g, "launch", { placeholder: "a program, shortcut or URL" })),
      field("Cover picture (optional)", textInput(g, "image", { placeholder: "a file path or https URL" })),
      h("div", { class: "actions-row" }, h("button", { type: "button", class: "primary", onclick: async () => {
        if (await act("game_add", { name: g.name, title: g.title, process: g.process, launch: g.launch, image: g.image }))
          { Object.assign(g, { name: "", title: "", process: "", launch: "", image: "" }); render(); }
      } }, "Add game"))),
  ];
}

// A credential kept in the Windows credential store: saved or not, add or remove.
let statusAsked = false;
function loadStatus() {
  if (!statusAsked) {
    statusAsked = true;
    act("secrets_status", {}, true).then((r) => { statusAsked = false; if (r) { ui.status = r; render(); } });
  }
  return h("p", { class: "hint" }, "Checking the credential store…");
}

function keyRow(label, slot, hint, statusKey, setAction, removeAction, argName) {
  if (!ui.status) return loadStatus();
  if (ui.status[statusKey]) {
    return h("div", { class: "form-row" }, h("p", { class: "hint align-end" }, `${label}: saved in the Windows credential store.`),
      h("button", { type: "button", class: "align-end", onclick: async () => {
        if (confirm(`Remove the ${label}?`) && await act(removeAction)) { ui.status[statusKey] = false; render(); }
      } }, "Remove"));
  }
  return h("div", { class: "form-row" }, field(label, secretInput(ui.keys, slot), hint),
    h("button", { type: "button", class: "align-end", onclick: async () => {
      if (await act(setAction, { [argName]: ui.keys[slot] })) { ui.keys[slot] = ""; ui.status[statusKey] = true; render(); }
    } }, "Check and save"));
}

// ---- AI, internet, GitHub and the board's address ---------------------------------------

function renderServices() {
  const s = svc();
  const agentText = { auto: "Whichever I used last", claude: "Claude Code", codex: "Codex" };
  const hooks = ui.status?.hooks;
  return [
    h("h2", {}, "AI, internet and GitHub"),
    h("h3", {}, "AI page"),
    h("div", { class: "radios" }, meta.agents.map((a) => h("label", {},
      h("input", { type: "radio", name: "agent", checked: s.agent === a, onchange: () => setSvc("agent", a) }), agentText[a] ?? a))),
    h("h3", {}, "Claude Code"),
    check("Live 5-hour and weekly limits, asked from Anthropic every minute (uses no tokens; the endpoint is undocumented)", "live_limits"),
    check("Alert on the board when a session needs a permission or is waiting for you", "alerts"),
    s.alerts ? h("div", { class: "form-row" }, field("Seconds a finished session waits before it alerts", number("idle_alert_seconds", 0, 3600))) : null,
    s.alerts ? (hooks ? h("div", { class: "form-row" },
      h("p", { class: "hint align-end" }, { missing: "The alerts need hooks in Claude Code's settings; they aren't there yet.",
                                            old: "Your Claude Code hooks are from an older version.",
                                            current: "Claude Code hooks are installed." }[hooks]),
      hooks !== "current" ? h("button", { type: "button", class: "align-end", onclick: async () => {
        if (await act("hooks_install")) { ui.status.hooks = "current"; render(); }
      } }, hooks === "old" ? "Update hooks" : "Add hooks") : null)
      : loadStatus()) : null,
    h("h3", {}, "Internet"),
    check("Check the connection (latency, jitter, packet loss)", "internet"),
    s.internet ? h("div", { class: "form-row" },
      field("Speed test every how many hours (0 = only when tapped)", number("speedtest_hours", 0, 168, 0.5))) : null,
    s.internet ? check("Show my public IP address", "show_ip") : null,
    h("h3", {}, "GitHub contributions"),
    keyRow("GitHub token", "github", "A fine-grained personal access token with no extra permissions (github.com/settings/personal-access-tokens/new).",
           "github_token", "github_token_set", "github_token_remove", "token"),
    h("div", { class: "radios", style: { marginTop: "10px" } }, meta.github_colors.map((c) => h("label", {},
      h("input", { type: "radio", name: "ghc", checked: s.github_colors === c, onchange: () => setSvc("github_colors", c) }),
      c === "green" ? "GitHub green" : "The board's amber"))),
    h("h3", {}, "Board address"),
    h("div", { class: "form-row" }, field("Host name or IP address", h("input", { type: "text", value: s.hub_host, spellcheck: "false",
      onchange: (e) => setSvc("hub_host", e.target.value.trim()) }), "deskhub.local, or the board's IP from your router if that name doesn't work.")),
    problemList("services"),
  ];
}

const EXTRA_VIEWS = { board: renderBoard, calendars: renderCalendars, printers: renderPrinters, games: renderGames,
                      services: renderServices };
