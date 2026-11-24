"use strict";
// The Desk Hub settings page. Talks to the companion's /api/state and /api/save;
// every call carries the token from the address the companion opened.

// Sections of config.toml the Save button writes.
const SECTION_NAMES = { home: "Home layout", pages: "Pages", tiles: "Shortcuts", display: "Screen and night",
                        services: "Options" };
// The page a Home widget needs; widgets for hidden pages stay off the board.
const WIDGET_PAGE = { claude: "ai", events: "calendar", weather: "weather", media: "media", stats: "stats",
                      printer: "printer", game: "games", net: "network", github: "github" };
const SWATCHES = ["#3a4256", "#2b2f3a", "#b4413c", "#2f6f5e", "#8a6d1f", "#5b3fa0", "#1f5f8a", "#8a2f6a"];

let token = "";
let meta = null, orig = null, cur = null, version = "", live = false, canRestart = false;
let needRestart = false;
let section = "home";
let problems = {};
let selWidget = -1, selTile = -1;

// ---- helpers ------------------------------------------------------------------

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
const icon = (name, cls) => h("span", { class: "mi" + (cls ? " " + cls : ""), "aria-hidden": "true" }, name);
const clone = (x) => JSON.parse(JSON.stringify(x));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const dirtySections = () => Object.keys(SECTION_NAMES).filter((s) => !same(cur[s], orig[s]));
const pageLabel = (id) => meta.pages.find((p) => p.id === id)?.label ?? id;
const widgetMeta = (id) => meta.widgets.find((w) => w.id === id);

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "X-Deskhub-Token": token, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = {};
  try { data = await res.json(); } catch { /* empty body */ }
  return { status: res.status, data };
}

let toastTimer = 0;
function toast(text, bad) {
  const t = document.getElementById("toast");
  t.textContent = text;
  t.className = "toast" + (bad ? " bad" : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, bad ? 9000 : 5000);
}

function changed() {
  const dirty = dirtySections();
  const bar = document.getElementById("savebar");
  bar.hidden = dirty.length === 0;
  document.getElementById("dirty").textContent =
    dirty.length ? "Unsaved: " + dirty.map((s) => SECTION_NAMES[s]).join(", ") : "";
  for (const a of document.querySelectorAll(".sections a")) {
    a.querySelector(".changed")?.remove();
    if (dirty.includes(a.dataset.section)) a.append(h("span", { class: "changed", title: "Unsaved changes" }, "•"));
  }
}

function update(fn) {
  fn();
  render();
  changed();
}

// ---- Home grid ----------------------------------------------------------------

function geometry(nav, header) {
  const side = nav !== "bottom";
  const pageX = nav === "left" ? 88 : 0;
  const pageW = side ? 712 : 800, pageH = side ? 480 : 412;
  const areaW = pageW - 40, contentH = pageH - 40;
  const gap = contentH < 400 ? 8 : 12;
  const top = header ? 44 + gap : 0;
  const areaH = contentH - top;
  const ox = pageX + 20, oy = 20 + top;
  const { cols, rows } = meta.grid;
  return {
    pageX, pageW, pageH, gap, ox, oy, areaW, areaH, header,
    rect(x, y, w, hh) {
      const x0 = Math.floor(x * (areaW + gap) / cols), x1 = Math.floor((x + w) * (areaW + gap) / cols) - gap;
      const y0 = Math.floor(y * (areaH + gap) / rows), y1 = Math.floor((y + hh) * (areaH + gap) / rows) - gap;
      return { left: ox + x0, top: oy + y0, width: x1 - x0, height: y1 - y0 };
    },
    cellAt(px, py) {
      return {
        x: Math.floor((px - ox) * cols / (areaW + gap)),
        y: Math.floor((py - oy) * rows / (areaH + gap)),
        inside: px >= ox && px < ox + areaW && py >= oy && py < oy + areaH,
      };
    },
  };
}

function gridProblem(items) {
  const taken = new Map();
  const { cols, rows } = meta.grid;
  for (const it of items) {
    const m = widgetMeta(it.widget);
    if (!m) return `${it.widget}: no such widget`;
    if (!m.widths.includes(it.w) || !m.heights.includes(it.h)) return `${m.label} doesn't come ${it.w}×${it.h}`;
    if (it.x < 0 || it.y < 0 || it.x + it.w > cols || it.y + it.h > rows) return `${m.label} runs off the grid`;
    for (let cx = it.x; cx < it.x + it.w; cx++) {
      for (let cy = it.y; cy < it.y + it.h; cy++) {
        const k = cx + "," + cy;
        if (taken.has(k)) return `${m.label} overlaps ${widgetMeta(taken.get(k)).label}`;
        taken.set(k, it.widget);
      }
    }
  }
  return null;
}

function fits(grid, skip, cand) {
  return !gridProblem(grid.filter((_, i) => i !== skip).concat([cand]));
}

const nearest = (list, v) => list.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a));

function widgetNote(id) {
  if (id === "clock" && cur.home.header) return "Hidden while the top bar is on";
  const page = WIDGET_PAGE[id];
  if (page && !cur.pages.enabled.includes(page)) return `Hidden: the ${pageLabel(page)} page is off`;
  return "";
}

function renderBoard() {
  const g = geometry(cur.pages.nav, cur.home.header);
  const board = h("div", { class: "board", role: "group", "aria-label": "Home screen preview, 800 by 480" });
  const wrap = h("div", { class: "board-wrap" }, board);

  // Navigation bar with the enabled pages.
  const side = cur.pages.nav !== "bottom";
  const rail = h("div", { class: "rail " + (side ? "side" : "bottom"),
                          style: side ? { left: cur.pages.nav === "left" ? "0" : "712px" } : {} });
  for (const p of cur.pages.enabled) {
    const pm = meta.pages.find((x) => x.id === p);
    rail.append(h("div", { class: "tab" + (p === "home" ? " on" : ""), title: pm.label }, icon(pm.icon)));
  }
  board.append(rail);

  if (g.header) {
    const now = new Date();
    board.append(h("div", { class: "header", style: { left: g.ox + "px", top: "20px", width: g.areaW + "px", height: "44px" } },
      h("span", {}, now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })),
      h("span", {}, now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" }))));
  }
  const { cols, rows } = meta.grid;
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      const r = g.rect(x, y, 1, 1);
      board.append(h("div", { class: "slot", style: px(r) }));
    }
  }
  cur.home.grid.forEach((it, i) => {
    const m = widgetMeta(it.widget);
    const note = widgetNote(it.widget);
    const el = h("div", {
      class: "widget" + (i === selWidget ? " selected" : ""), style: px(g.rect(it.x, it.y, it.w, it.h)),
      tabindex: "0", role: "button", "aria-label": `${m.label}, ${it.w} by ${it.h}, at column ${it.x + 1} row ${it.y + 1}`,
      onkeydown: (e) => widgetKey(e, i),
    },
      h("div", { class: "name" }, icon(m.icon), m.label),
      note ? h("div", { class: "off" }, note) : h("div", { class: "size" }, `${it.w} × ${it.h}`),
      h("div", { class: "grip", title: "Drag to resize" }, icon("south_east")));
    el.addEventListener("pointerdown", (e) => startDrag(e, board, g, e.target.closest(".grip") ? "resize" : "move", i));
    board.append(el);
  });
  requestAnimationFrame(() => fitBoard(wrap, board));
  return wrap;
}

function px(r) {
  return { left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px" };
}

function fitBoard(wrap, board) {
  const s = Math.min(1, wrap.clientWidth / 800);
  board.style.transform = `scale(${s})`;
  wrap.style.height = 480 * s + "px";
  board.dataset.scale = s;
}
window.addEventListener("resize", () => {
  const b = document.querySelector(".board");
  if (b) fitBoard(b.parentElement, b);
});

// One drag at a time: moving or resizing a placed widget, or adding one from the list.
function startDrag(e, board, g, mode, index, widget) {
  if (e.button !== 0) return;
  e.preventDefault();
  const grid = cur.home.grid;
  const it = index >= 0 ? grid[index] : null;
  const m = widgetMeta(it ? it.widget : widget);
  const toBoard = (ev) => {
    const r = board.getBoundingClientRect(), s = parseFloat(board.dataset.scale || "1");
    return { x: (ev.clientX - r.left) / s, y: (ev.clientY - r.top) / s };
  };
  const start = toBoard(e);
  const grab = it ? g.cellAt(start.x, start.y) : null;
  const ghost = h("div", { class: "ghost", hidden: true });
  board.append(ghost);
  const srcEl = e.currentTarget;
  srcEl.setPointerCapture(e.pointerId);
  let cand = null, moved = false;

  const onMove = (ev) => {
    const p = toBoard(ev);
    if (Math.abs(p.x - start.x) + Math.abs(p.y - start.y) > 6) moved = true;
    if (!moved) return;
    if (it && mode === "move") srcEl.classList.add("dragging");
    const c = g.cellAt(p.x, p.y);
    if (mode === "resize") {
      cand = { ...it, w: nearest(m.widths, c.x - it.x + 1), h: nearest(m.heights, c.y - it.y + 1) };
    } else if (!c.inside) {
      cand = null;
    } else if (it) {
      cand = { ...it, x: it.x + c.x - grab.x, y: it.y + c.y - grab.y };
    } else {
      cand = { widget, x: c.x, y: c.y, w: m.widths[0], h: m.heights[0] };
    }
    if (!cand) { ghost.hidden = true; return; }
    ghost.hidden = false;
    Object.assign(ghost.style, px(g.rect(cand.x, cand.y, cand.w, cand.h)));
    ghost.classList.toggle("bad", !fits(grid, index, cand));
  };
  const onUp = () => {
    srcEl.removeEventListener("pointermove", onMove);
    srcEl.removeEventListener("pointerup", onUp);
    srcEl.removeEventListener("pointercancel", onUp);
    ghost.remove();
    srcEl.classList.remove("dragging");
    if (!moved) {
      if (it) update(() => { selWidget = index; });
      return;
    }
    if (it && mode === "move" && !cand) {
      update(() => { grid.splice(index, 1); selWidget = -1; });   // dragged off the board
    } else if (cand && fits(grid, index, cand)) {
      update(() => {
        if (it) grid[index] = cand; else grid.push(cand);
        selWidget = it ? index : grid.length - 1;
      });
    }
  };
  srcEl.addEventListener("pointermove", onMove);
  srcEl.addEventListener("pointerup", onUp);
  srcEl.addEventListener("pointercancel", onUp);
}

function widgetKey(e, i) {
  const it = cur.home.grid[i];
  const step = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
  if (step) {
    e.preventDefault();
    const cand = { ...it, x: it.x + step[0], y: it.y + step[1] };
    if (fits(cur.home.grid, i, cand)) update(() => { cur.home.grid[i] = cand; selWidget = i; });
    document.querySelectorAll(".board .widget")[i]?.focus();
  } else if (e.key === "Delete" || e.key === "Backspace") {
    update(() => { cur.home.grid.splice(i, 1); selWidget = -1; });
  } else if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    update(() => { selWidget = i; });
    document.querySelectorAll(".board .widget")[i]?.focus();
  }
}

function addWidget(id) {
  const m = widgetMeta(id);
  const { cols, rows } = meta.grid;
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      const cand = { widget: id, x, y, w: m.widths[0], h: m.heights[0] };
      if (fits(cur.home.grid, -1, cand)) {
        update(() => { cur.home.grid.push(cand); selWidget = cur.home.grid.length - 1; });
        return;
      }
    }
  }
  toast(`No free space for ${m.label}. Make room first.`, true);
}

function renderHome() {
  const placed = new Set(cur.home.grid.map((g) => g.widget));
  const board = renderBoard();
  const palette = h("div", { class: "palette" });
  const free = meta.widgets.filter((w) => !placed.has(w.id));
  if (!free.length) palette.append(h("p", { class: "empty" }, "Every widget is on Home."));
  for (const w of free) {
    const note = widgetNote(w.id);
    const chip = h("div", { class: "chip", tabindex: "0", role: "button", title: note || "Drag onto Home, or press Enter",
                            onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); addWidget(w.id); } } },
      icon(w.icon), w.label, h("small", {}, `${w.widths[0]}×${w.heights[0]}`));
    chip.addEventListener("pointerdown", (e) => {
      const b = document.querySelector(".board");
      startDrag(e, b, geometry(cur.pages.nav, cur.home.header), "add", -1, w.id);
    });
    palette.append(chip);
  }

  const side = h("div", { class: "side" });
  const sel = cur.home.grid[selWidget];
  if (sel) {
    const m = widgetMeta(sel.widget);
    const sizes = [];
    for (const hh of m.heights) for (const w of m.widths) {
      const cand = { ...sel, w, h: hh };
      if (fits(cur.home.grid, selWidget, cand)) sizes.push(cand);
    }
    side.append(h("h3", {}, m.label),
      h("div", { class: "selected-panel" },
        h("label", { class: "field" }, h("span", {}, "Size (columns × rows)"),
          h("select", { onchange: (e) => update(() => { const [w, hh] = e.target.value.split("x").map(Number);
                                                          cur.home.grid[selWidget] = { ...sel, w, h: hh }; }) },
            sizes.map((c) => h("option", { value: `${c.w}x${c.h}`, selected: c.w === sel.w && c.h === sel.h }, `${c.w} × ${c.h}`)))),
        h("p", { class: "hint" }, "Drag to move it, drag its corner to resize. Arrow keys move it too."),
        h("div", {}, h("button", { type: "button", onclick: () => update(() => { cur.home.grid.splice(selWidget, 1); selWidget = -1; }) },
          "Take off Home"))));
  }
  side.append(h("h3", {}, "Not on Home"), palette,
    h("p", { class: "hint" }, "Drag one onto a free spot. Drag a widget off the board to remove it."));

  return [
    h("h2", {}, "Home layout"),
    h("p", { class: "lead" }, "Home is a grid of 5 columns by 3 rows. This is the board at its real size, 800 × 480."),
    h("label", { class: "toggle" },
      h("input", { type: "checkbox", checked: cur.home.header, onchange: (e) => update(() => { cur.home.header = e.target.checked; }) }),
      "Time and date in a slim bar across the top (instead of the Clock widget)"),
    h("div", { class: "home-layout", style: { marginTop: "16px" } }, board, side),
    problemList("home"),
  ];
}

// ---- Pages --------------------------------------------------------------------

function renderPages() {
  const enabled = cur.pages.enabled;
  const order = enabled.concat(meta.pages.map((p) => p.id).filter((p) => !enabled.includes(p)));
  const list = h("ul", { class: "page-list" });
  let dragFrom = null;
  order.forEach((id) => {
    const pm = meta.pages.find((p) => p.id === id);
    const on = enabled.includes(id);
    const idx = enabled.indexOf(id);
    const move = (d) => update(() => {
      const e = cur.pages.enabled, j = idx + d;
      [e[idx], e[j]] = [e[j], e[idx]];
    });
    const li = h("li", { class: on ? "" : "hidden-page", draggable: on && id !== "home" ? "true" : false },
      h("input", { type: "checkbox", checked: on, disabled: id === "home", "aria-label": `Show ${pm.label}`,
                   onchange: (e) => update(() => {
                     cur.pages.enabled = e.target.checked ? enabled.concat([id]) : enabled.filter((p) => p !== id);
                   }) }),
      icon(pm.icon), pm.label,
      on && id !== "home" ? h("span", { class: "move" },
        h("button", { type: "button", class: "icon", title: "Move up", "aria-label": `Move ${pm.label} up`,
                      disabled: idx <= 1, onclick: () => move(-1) }, icon("arrow_upward")),
        h("button", { type: "button", class: "icon", title: "Move down", "aria-label": `Move ${pm.label} down`,
                      disabled: idx >= enabled.length - 1, onclick: () => move(1) }, icon("arrow_downward"))) : null);
    if (on && id !== "home") {
      li.addEventListener("dragstart", (e) => { dragFrom = id; e.dataTransfer.effectAllowed = "move"; });
      li.addEventListener("dragover", (e) => { if (dragFrom) { e.preventDefault(); li.classList.add("drag-over"); } });
      li.addEventListener("dragleave", () => li.classList.remove("drag-over"));
      li.addEventListener("drop", (e) => {
        e.preventDefault();
        if (!dragFrom || dragFrom === id) return;
        update(() => {
          const e2 = cur.pages.enabled.filter((p) => p !== dragFrom);
          e2.splice(e2.indexOf(id), 0, dragFrom);
          cur.pages.enabled = e2;
        });
      });
    }
    list.append(li);
  });
  const navLabels = { left: "Left", right: "Right", bottom: "Along the bottom" };
  return [
    h("h2", {}, "Pages"),
    h("p", { class: "lead" }, "Which pages the board shows, in navigation bar order. Home is always first. Drag a page or use the arrows to reorder."),
    list,
    h("h3", {}, "Navigation bar"),
    h("div", { class: "radios", role: "radiogroup", "aria-label": "Navigation bar position" },
      meta.nav.map((n) => h("label", {},
        h("input", { type: "radio", name: "nav", value: n, checked: cur.pages.nav === n,
                     onchange: () => update(() => { cur.pages.nav = n; }) }), navLabels[n] ?? n))),
    h("p", { class: "hint" }, "The board restarts once when this changes, to lay its pages out for the new space."),
    problemList("pages"),
  ];
}

// ---- Shortcuts ----------------------------------------------------------------

function tileView(t, i) {
  return h("button", { type: "button", class: "tile" + (i === selTile ? " selected" : ""), style: { background: t.color },
                       onclick: () => update(() => { selTile = i; }), "aria-label": `Edit ${t.label || "tile " + (i + 1)}` },
    icon(t.icon), h("span", {}, t.label || " "));
}

function renderTileForm() {
  const t = cur.tiles[selTile];
  if (!t) return h("p", { class: "hint" }, "Pick a tile to change it, or add one.");
  const act = meta.actions.find((a) => a.id === t.action);
  const set = (k, v) => update(() => { cur.tiles[selTile][k] = v; });
  const setAction = (a) => update(() => {
    const was = meta.default_icon[t.action + ":" + t.target] ?? meta.default_icon[t.action];
    const am = meta.actions.find((x) => x.id === a);
    t.action = a;
    t.target = am?.choices ? am.choices[0] : (am?.target ? t.target : "");
    if (!t.icon || t.icon === was || t.icon === "apps") t.icon = meta.default_icon[a + ":" + t.target] ?? meta.default_icon[a] ?? t.icon;
  });
  let target = null;
  if (act?.choices) {
    target = h("label", { class: "field" }, h("span", {}, act.target),
      h("select", { onchange: (e) => update(() => {
        const was = meta.default_icon[t.action + ":" + t.target];
        t.target = e.target.value;
        if (t.icon === was) t.icon = meta.default_icon[t.action + ":" + t.target] ?? t.icon;
      }) }, act.choices.map((c) => h("option", { value: c, selected: c === t.target }, c))));
  } else if (act?.target) {
    target = h("label", { class: "field" }, h("span", {}, act.target),
      h("input", { type: "text", value: t.target, spellcheck: "false", onchange: (e) => set("target", e.target.value) }));
  }
  const n = cur.tiles.length;
  const move = (d) => update(() => {
    const j = selTile + d;
    [cur.tiles[selTile], cur.tiles[j]] = [cur.tiles[j], cur.tiles[selTile]];
    selTile = j;
  });
  return h("div", { class: "tile-form" },
    h("label", { class: "field" }, h("span", {}, "Label"),
      h("input", { type: "text", value: t.label, maxlength: "30", onchange: (e) => set("label", e.target.value) })),
    h("label", { class: "field" }, h("span", {}, "What a tap does"),
      h("select", { onchange: (e) => setAction(e.target.value) },
        !act ? h("option", { value: "", selected: true }, "Pick one") : null,
        meta.actions.map((a) => h("option", { value: a.id, selected: a.id === t.action }, a.help)))),
    target,
    h("div", { class: "field" }, h("span", { class: "hint" }, "Icon"),
      h("div", { class: "icon-pick", role: "group", "aria-label": "Icon" },
        meta.icons.map((name) => h("button", { type: "button", title: name, "aria-label": name, "aria-pressed": String(t.icon === name),
                                               onclick: () => set("icon", name) }, icon(name))))),
    h("div", { class: "field" }, h("span", { class: "hint" }, "Colour"),
      h("div", { class: "swatches" },
        SWATCHES.map((c) => h("button", { type: "button", style: { background: c }, title: c, "aria-label": c,
                                          "aria-pressed": String(t.color.toLowerCase() === c), onclick: () => set("color", c) })),
        h("input", { type: "color", value: /^#[0-9a-f]{6}$/i.test(t.color) ? t.color : "#3a4256", "aria-label": "Other colour",
                     onchange: (e) => set("color", e.target.value) }))),
    h("div", { class: "row" },
      h("button", { type: "button", disabled: selTile === 0, onclick: () => move(-1) }, "Move earlier"),
      h("button", { type: "button", disabled: selTile === n - 1, onclick: () => move(1) }, "Move later"),
      h("button", { type: "button", onclick: () => update(() => { cur.tiles.splice(selTile, 1); selTile = Math.min(selTile, cur.tiles.length - 1); }) },
        "Delete tile")));
}

function renderTiles() {
  const grid = h("div", { class: "tile-grid" }, cur.tiles.map(tileView));
  if (cur.tiles.length < meta.max_tiles) {
    grid.append(h("button", { type: "button", class: "tile add", onclick: () => update(() => {
      cur.tiles.push({ label: "New tile", icon: "keyboard", color: "#3a4256", action: "keys", target: "" });
      selTile = cur.tiles.length - 1;
    }) }, icon("add"), h("span", {}, "Add tile")));
  }
  return [
    h("h2", {}, "Shortcuts"),
    h("p", { class: "lead" }, `Buttons on the Shortcuts page that do something on this PC. Up to ${meta.max_tiles}; 2, 4, 6, 8, 12 or 16 make an even grid.`),
    h("div", { class: "tiles-layout" }, grid, renderTileForm()),
    problemList("tiles"),
  ];
}

// ---- Screen and night ---------------------------------------------------------

function renderDisplay() {
  const d = cur.display;
  const [start, end] = d.night ? d.night.split("-") : ["", ""];
  const setNight = (s, e) => update(() => { d.night = s && e ? `${s}-${e}` : ""; });
  const sleepText = { off: "Turn the screen off", clock: "Show a dim clock", none: "Stay as it is" };
  const nightText = { off: "Screen off", clock: "A dim clock" };
  return [
    h("h2", {}, "Screen and night"),
    h("h3", {}, "While the PC's display is asleep"),
    h("div", { class: "radios" }, meta.pc_sleep.map((m) => h("label", {},
      h("input", { type: "radio", name: "pcs", checked: d.pc_sleep === m, onchange: () => update(() => { d.pc_sleep = m; }) }),
      sleepText[m] ?? m))),
    h("p", { class: "hint" }, "A touch brings the board back for a minute."),
    h("h3", {}, "Night mode"),
    h("label", { class: "toggle" },
      h("input", { type: "checkbox", checked: !!d.night, onchange: (e) => setNight(e.target.checked ? "23:00" : "", "07:00") }),
      "Go dark every night, whether or not the PC is on"),
    d.night ? h("div", { class: "row", style: { display: "flex", gap: "14px", marginTop: "12px" } },
      h("label", { class: "field" }, h("span", {}, "From"),
        h("input", { type: "time", value: start, onchange: (e) => setNight(e.target.value, end) })),
      h("label", { class: "field" }, h("span", {}, "Until"),
        h("input", { type: "time", value: end, onchange: (e) => setNight(start, e.target.value) }))) : null,
    d.night ? h("div", { class: "radios", style: { marginTop: "14px" } }, meta.night_style.map((m) => h("label", {},
      h("input", { type: "radio", name: "ns", checked: d.night_style === m, onchange: () => update(() => { d.night_style = m; }) }),
      nightText[m] ?? m))) : null,
    problemList("display"),
  ];
}

// ---- page ---------------------------------------------------------------------

function problemList(s) {
  return problems[s]?.length ? h("ul", { class: "problems" }, problems[s].map((p) => h("li", {}, p))) : null;
}

function render() {
  const main = document.getElementById("main");
  const views = { home: renderHome, pages: renderPages, tiles: renderTiles, display: renderDisplay, ...EXTRA_VIEWS };
  const view = [restartBar(), ...views[section]()];
  const focusedLabel = document.activeElement?.getAttribute?.("aria-label");
  main.replaceChildren(...view.filter(Boolean));
  if (focusedLabel) main.querySelector(`[aria-label="${CSS.escape(focusedLabel)}"]`)?.focus();
  for (const a of document.querySelectorAll(".sections a")) {
    if (a.dataset.section === section) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
}

async function save() {
  const dirty = dirtySections();
  if (!dirty.length) return;
  const btn = document.getElementById("save");
  btn.disabled = true;
  try {
    const state = Object.fromEntries(dirty.map((s) => [s, cur[s]]));
    const { status, data } = await api("/api/save", { version, state });
    if (status === 400 && data.problems) {
      problems = data.problems;
      const first = Object.keys(problems)[0];
      section = first;
      location.hash = first;
      render();
      toast(`Not saved. ${SECTION_NAMES[first]}: ${problems[first][0]}`, true);
      return;
    }
    if (status !== 200) {
      toast(data.error || `Not saved (error ${status}).`, true);
      return;
    }
    problems = {};
    version = data.version;
    for (const s of dirty) orig[s] = clone(cur[s]);
    render();
    changed();
    if ((data.notes || []).some((n) => n.includes("Restart"))) needRestart = true;
    render();
    const how = data.applied ? "Saved, and the board has it." : live ? "Saved." :
      "Saved to config.toml. The board gets it when the companion starts.";
    toast([how, ...(data.notes || [])].join(" "));
  } catch (e) {
    toast("Can't reach the companion. Is it still running?", true);
  } finally {
    btn.disabled = false;
  }
}

async function load() {
  const { status, data } = await api("/api/state");
  if (status !== 200) {
    document.getElementById("main").replaceChildren(h("p", { class: "error" }, data.error || `Can't load settings (error ${status}).`));
    return;
  }
  meta = data.meta;
  orig = data.state;
  cur = clone(orig);
  version = data.version;
  live = data.live;
  canRestart = data.can_restart;
  document.getElementById("where").textContent =
    `${data.path} · board at ${orig.hub.host}` + (live ? "" : " · companion not running: changes apply when it starts");
  render();
  changed();
}

function route() {
  const s = location.hash.slice(1);
  if (SECTION_NAMES[s] || EXTRA_VIEWS[s]) section = s;
  if (cur) render();
}

(function init() {
  const m = location.hash.match(/^#t=([\w-]+)/);
  if (m) {
    sessionStorage.setItem("deskhub-token", m[1]);
    history.replaceState(null, "", "#home");
  }
  token = sessionStorage.getItem("deskhub-token") || "";
  route();
  window.addEventListener("hashchange", route);
  document.getElementById("save").addEventListener("click", save);
  document.getElementById("discard").addEventListener("click", () => update(() => {
    cur = clone(orig); problems = {}; selWidget = -1; selTile = -1;
  }));
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); save(); }
  });
  window.addEventListener("beforeunload", (e) => { if (cur && dirtySections().length) e.preventDefault(); });
  load();
})();
