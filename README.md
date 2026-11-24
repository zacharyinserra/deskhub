# Desk Hub

A desk display for the **Waveshare ESP32-S3-Touch-LCD-4.3B**. It shows the time, weather, your calendar, what's playing on your PC, CPU and GPU load, and your Claude Code usage. It also gives you a grid of buttons that run things on your PC.

https://github.com/user-attachments/assets/2b18951c-0adb-42aa-9e92-08439c5763bc

The board runs custom firmware (ESP-IDF + LVGL). A small Python app on your Windows PC, the *companion*, sends it PC data over your Wi-Fi. The clock and weather keep working when the PC is off.

| | |
| --- | --- |
| ![PC stats](docs/screenshots/stats.png) | ![Claude Code usage](docs/screenshots/ai.png) |
| ![Calendar](docs/screenshots/calendar.png) | ![Now playing](docs/screenshots/media.png) |
| ![3D printer](docs/screenshots/printer.png) | ![Shortcuts](docs/screenshots/shortcuts.png) |
| ![Timer](docs/screenshots/timer.png) | ![Waiting alert](docs/screenshots/alert.png) |
| ![Games](docs/screenshots/games.png) | ![Internet](docs/screenshots/network.png) |
| ![Home](docs/screenshots/home.png) | ![GitHub](docs/screenshots/github.png) |
| ![Weather](docs/screenshots/weather.png) | ![Codex usage](docs/screenshots/codex.png) |

## Contents

- [Features](#features)
- [What you need](#what-you-need)
- [Setup](#setup)
  - [1. Install the tools](#1-install-the-tools)
  - [2. Get the code](#2-get-the-code)
  - [3. Run setup](#3-run-setup)
  - [Changing one thing](#changing-one-thing)
  - [Updating the firmware](#updating-the-firmware)
  - [4. Start the companion](#4-start-the-companion)
  - [Start the companion with Windows](#start-the-companion-with-windows)
- [Commands](#commands)
- [Calendars](#calendars)
- [Choosing pages](#choosing-pages)
- [When the PC sleeps](#when-the-pc-sleeps) and [Night mode](#night-mode)
- [Steam](#steam) and [Games that aren't on Steam](#games-that-arent-on-steam)
- [Internet](#internet) and [GitHub contributions](#github-contributions)
- [Plex and Jellyfin](#plex-and-jellyfin)
- [Customizing Home](#customizing-home)
- [3D printer](#3d-printer)
- [Claude Code usage](#claude-code-usage), [Codex](#codex) and [Waiting alerts](#waiting-alerts)
- [Shortcuts](#shortcuts)
- [Troubleshooting](#troubleshooting)
- [How it works](#how-it-works)
- [Development](#development) and [Hardware notes](#hardware-notes-43b)
- [Roadmap](#roadmap), [License](#license) and [Credits](#credits)

## Features

| Page | What it shows | Where the data comes from |
| --- | --- | --- |
| Home | Clock, date, Claude limits, next events, weather, now playing, CPU/GPU/RAM | everything below |
| PC stats | CPU, GPU, RAM and VRAM gauges, GPU temperature, a one-minute history chart, network and disk | companion |
| AI | Claude Code or Codex 5-hour and weekly limits with reset times, tokens today, a 7-day chart, usage per model | companion, from Claude Code or Codex |
| Calendar | Up to 16 upcoming events, grouped by day, from the next 7 days or as many as you set | companion, from Google, Apple iCloud, Outlook or any ICS feed |
| Weather | Current conditions, the next 24 hours and 6 days | the board itself, from [Open-Meteo](https://open-meteo.com) |
| Media | Whatever Windows lists as playing (Spotify, YouTube in a browser, VLC…) with the cover, a seek bar and controls; with nothing playing on the PC, what plays on your [Plex or Jellyfin server](#plex-and-jellyfin) | companion |
| Shortcuts | Up to 16 buttons: key combos, apps, folders, URLs, volume, media, lock PC | companion |
| 3D printer | Print state, progress, temperatures and filament colours for up to 4 printers: Bambu Lab, Klipper, Prusa, OctoPrint, Flashforge, Elegoo, Snapmaker, Anycubic, Creality (optional) | companion, over the local network (Bambu also through its cloud) |
| Games | The Steam game you're playing with its cover and session time, your five most recent games, and a tap to launch one (optional) | companion, from Steam's local files |
| Stats: Internet view | Online status, latency, jitter and packet loss with a one-minute chart, uptime and the last drop, data used today and this month, and an on-demand speed test | companion |
| Timer | Countdown with presets from 1 to 45 minutes, pause and reset, and a full-screen "Time's up" card. The time left shows on its sidebar tab | the board itself, works without the PC |
| GitHub | Your contribution chart for the whole year with month and weekday labels, contributions by kind, your current and longest streak and best day, this week against last week day by day, and your top repositories by commits; plus a Home widget (optional) | companion, from GitHub's API with your token |

Home is a 5 × 3 grid you arrange yourself, with widgets in the sizes you choose ([Customizing Home](#customizing-home)). Beyond the pages:

- [Waiting alerts](#waiting-alerts) show when a Claude Code session needs a permission or a reply.
- The board goes dark or shows a dim clock while the PC's screen sleeps or during night hours ([When the PC sleeps](#when-the-pc-sleeps)).
- New firmware goes over Wi-Fi and installs only after you tap the board ([Updating the firmware](#updating-the-firmware)).
- The companion can start hidden with Windows, with an icon in the notification area ([Start the companion with Windows](#start-the-companion-with-windows)).

## What you need

- A [Waveshare ESP32-S3-Touch-LCD-4.3B](https://www.waveshare.com/esp32-s3-touch-lcd-4.3b.htm). This is the **B** model (800 × 480, capacitive touch). Other boards have different wiring and won't work without changes.
- A USB-C **data** cable. Some cables only carry power.
- A Windows 10/11 PC on the same network. NVIDIA GPU stats need an NVIDIA driver; everything else works on any PC.
- A **2.4 GHz** Wi-Fi network. The ESP32-S3 can't join 5 GHz networks.

## Setup

### 1. Install the tools

1. **Git**: [git-scm.com](https://git-scm.com/download/win).
2. **uv**, which runs the companion and installs its Python: [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/). In PowerShell:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. **ESP-IDF v5.5**, Espressif's toolchain for building the firmware. Use the [ESP-IDF Windows installer](https://dl.espressif.com/dl/esp-idf/). Choose version **5.5**, target **ESP32-S3**, and keep the default install folder. Setup looks for ESP-IDF in `C:\Espressif\frameworks\esp-idf-*`, `C:\esp\v5.5\esp-idf`, `%USERPROFILE%\esp\esp-idf-*`, and the folder named by the `IDF_PATH` environment variable.

In this README, `~` means your user folder, `C:\Users\<you>`.

### 2. Get the code

```powershell
git clone https://github.com/zacharyinserra/deskhub.git
cd deskhub\companion
```

Clone to a short path such as `C:\Code\deskhub`. Very long Windows paths break some of the Python packages.

### 3. Run setup

Plug the board into your PC with the USB-C cable. If your board has two USB-C ports, use the one labeled **USB**, not **UART**. Then run:

```powershell
uv run deskhub-setup
```

It asks these questions in order. When you run it again, each answer you gave before shows in brackets, and Enter keeps it. On the first run the answers start blank.

1. **Wi-Fi**: the network name, then the password. The password stays hidden as you type, and pressing Enter keeps the saved one. The hub needs a WPA password of 8 to 63 characters, so open networks aren't supported.
2. **City**: type something like `Charlotte, NC` or `Paris, France` and pick from the matches. This sets the weather location and the time zone.
3. **Units**: two yes/no questions. The first asks "Fahrenheit and mph", which defaults to yes for US cities. The second asks "24-hour clock".
4. **Calendars**: setup asks whether you want to add Google or Apple calendars now. See [Calendars](#calendars).
5. **3D printers**: whether to add or change 3D printers. See [3D printer](#3d-printer).
6. **Games**: whether to add games that aren't on Steam, such as Minecraft. See [Games that aren't on Steam](#games-that-arent-on-steam).
7. **Shortcuts**: whether to add, change, move or remove the buttons on the Shortcuts page. See [Shortcuts](#shortcuts).
8. **Pages**: a yes/no for each page, to choose which ones the sidebar shows (Home is always shown), then where the navigation bar goes: `left`, `right` or `bottom`. Moving it restarts the board once so every page is laid out for the new space; with the bar along the bottom, pages use a slightly more compact layout.
9. **Home screen**: whether the time and date go in a slim top bar, then whether to keep the current layout. To change it, add widgets one at a time with a size each; `undo` takes the last one off and `clear` starts over. See [Customizing Home](#customizing-home).
10. **Screen sleep and night mode**: whether the board goes dark (`off`), shows a dim clock (`clock`) or stays as it is (`none`) while the PC's screen sleeps, then night-mode hours such as `23:00-07:00` (or `off`) and what it shows at night. See [When the PC sleeps](#when-the-pc-sleeps).
11. **Internet**: how often to run a speed test (`0`, the default, runs one only when you tap the button) and whether to show your public IP. See [Internet](#internet).
12. **GitHub**: whether to add a token for the contribution chart, whether to show the GitHub page, then whether to put the chart on Home. See [GitHub contributions](#github-contributions).
13. **Claude Code limits**: whether to turn on live limits. See [Claude Code usage](#claude-code-usage).
14. **Waiting alerts**: whether the board shows when a Claude Code session is waiting for you. Setup offers to add the hooks to Claude Code's settings, update hooks from an older version, or remove them when you turn alerts off. See [Waiting alerts](#waiting-alerts).
15. **AI agent**: which agent the AI page shows: `auto`, `claude` or `codex`.
16. **Build and flash**: setup asks before it builds. Once the board runs Desk Hub, the new firmware goes over Wi-Fi and the board asks you to tap **Install**. The first time, or when Wi-Fi can't work, it uses USB: setup finds the board's port, or asks for the COM port if it can't tell (Device Manager lists it under *Ports*). The first build takes a few minutes.
17. **Start with Windows**: whether the companion starts by itself, hidden, when you sign in. See [Start the companion with Windows](#start-the-companion-with-windows).

Setup also creates `companion/config.toml` and gives the board and the companion a shared random token, so they can trust each other.

#### Changing one thing

To change one part without going through all of setup, name it:

```powershell
uv run deskhub-setup calendar
```

| Topic | What it changes |
| --- | --- |
| `wifi` | Wi-Fi network and password |
| `weather` | city, time zone and units (also `city`, `units`) |
| `clock` | 12- or 24-hour clock (also `time`) |
| `screen` | turn the screen off after so many idle minutes, or never (also `timeout`) |
| `hub` | the board's address, for when `deskhub.local` doesn't work; checks that the board answers |
| `calendar` | opens the calendar menu, then how many days ahead to show (also `calendars`, `events`) |
| `printer` | opens the 3D printer menu (also `printers`) |
| `media` | Plex and Jellyfin servers for the Media page (also `plex`, `jellyfin`) |
| `games` | games that aren't on Steam, which [built-in games](#games-that-arent-on-steam) to recognise, and the Steam Web API key (also `presets`) |
| `steam` | Steam games on or off, and the Steam Web API key |
| `shortcuts` | the buttons on the Shortcuts page (also `tiles`) |
| `pages` | which pages show, and where the navigation bar goes |
| `home` | the Home grid and the top bar (also `grid`) |
| `display` | screen sleep with the PC, and night mode (also `sleep`, `night`) |
| `internet` | connection checks on or off, speed test schedule and public IP (also `network`) |
| `github` | the GitHub token, the GitHub page, and the contribution chart on Home (also `contributions`) |
| `claude` | live limits, waiting alerts and the AI page's agent (also `ai`, `codex`) |
| `alerts` | waiting alerts, and how long a finished session waits before it alerts |
| `flash` | builds the firmware and installs it on the board |
| `startup` | starting the companion with Windows |

PC stats and the timer have nothing to set. `wifi`, `weather`, `clock` and `screen` live in the firmware, so after them setup offers to build and install it. The others change `config.toml`; restart the companion afterwards (tray icon → **Restart**) to use them. `uv run deskhub-setup --help` lists the topics too.

If setup says it can't find ESP-IDF, or the flash fails, you can flash by hand. Open PowerShell in the repo's `firmware\` folder and run these two lines, changing the path to match your ESP-IDF version and the port to match your board:

```powershell
. C:\Espressif\frameworks\esp-idf-v5.5.1\export.ps1
idf.py -p COM5 flash
```

### Updating the firmware

After pulling new code, or changing a setting that lives in the firmware, run:

```bash
uv run deskhub-flash
```

It builds the firmware and sends it to the board over Wi-Fi. The board shows **Install a firmware update?**: tap **Install** within a minute and it installs, then restarts; **Deny** leaves it as it is. Nothing is installed without that tap, and the upload needs the board's token. If the board isn't reachable, runs firmware from before Wi-Fi updates, or no longer accepts the token, `deskhub-flash` falls back to USB. Use `--usb` to go straight to USB, `--port COM5` to pick the USB port when more than one board is plugged in, and `--no-build` to send the last build again.

If a new firmware can't start properly, the board goes back to the previous one by itself on the next restart.

### 4. Start the companion

```powershell
uv run python -m deskhub
```

Within a few seconds the monitor icon near the bottom of the board's sidebar, just above the Wi-Fi icon, turns green. The stats, media and calendar pages then fill in. Leave this window open while you use the board, and run other commands such as `uv run deskhub-calendars` in a second terminal. To have it start by itself instead, hidden in the background, see [Start the companion with Windows](#start-the-companion-with-windows).

Options: `--config <path>` uses another config file, `--tray` shows the notification-area icon, `--log <path>` writes a log file, and `-v` logs more detail.

Start it with `python -m deskhub` as shown, not `uv run deskhub`. The `deskhub.exe` launcher stays locked while the companion runs, so any later `uv run` that needs to update the project fails with "Access is denied".

To change anything later, run `uv run deskhub-setup` again, or just one part of it, such as `uv run deskhub-setup home` (see [Changing one thing](#changing-one-thing)).

### Start the companion with Windows

```bash
uv run deskhub-install
```

This puts a shortcut in your Startup folder that runs the companion hidden (with `pythonw`, so no terminal window) each time you sign in. Setup offers it as its last step. Without a console, the companion logs to `~/.deskhub/companion.log`. To undo it:

```bash
uv run deskhub-install --remove
```

The hidden companion shows an icon in the notification area by the clock: amber while the board is connected, grey while it isn't, with the board's name and IP in its tooltip. Right-click it for **Settings**, **Edit config**, **Run setup**, **Restart** (picks up config changes), **Open log** and **Quit**; double-click opens Settings. Run `uv run python -m deskhub --tray` to get the icon from a terminal too.

Only one companion runs at a time: if the hidden one is already running, starting another in a terminal stops with a message, because two would keep knocking each other off the board.

## Commands

Run these in `companion/`.

| Command | What it does |
| --- | --- |
| `uv run python -m deskhub` | Runs the companion. |
| `uv run deskhub-setup` | Walks through every setting, then builds and flashes the firmware. |
| `uv run deskhub-setup <topic>` | Runs one part of setup, such as `calendar`, `weather` or `home`. See [Changing one thing](#changing-one-thing). |
| `uv run deskhub-flash` | Builds the firmware and sends it to the board over Wi-Fi, or USB. |
| `uv run deskhub-install` | Starts the companion with Windows; `--remove` stops that. |
| `uv run deskhub-config` | Opens the settings page in your browser: Home layout, pages, shortcut tiles, screen and night mode. With the companion running, saved changes reach the board at once. |
| `uv run deskhub-calendars` | Lists, adds and removes calendars. |
| `uv run deskhub-printers` | Adds and removes 3D printers. |
| `uv run deskhub-games` | Adds a game that isn't on Steam, picked from the programs running now. |
| `uv run python install_claude.py` | Installs the Claude Code status line and hooks; `statusline`, `hooks` and `--remove` narrow it down. |

## Calendars

Setup offers this step. You can also run it on its own:

```powershell
uv run deskhub-calendars
```

That opens a menu to list, add and remove calendars. Restart the companion afterwards.

- **Google Calendar**: on [calendar.google.com](https://calendar.google.com), open Settings, pick your calendar, go to *Integrate calendar*, and copy the **Secret address in iCal format**. Choose *Add Google Calendar* and paste it. The helper fetches it once to check that it works.
- **Apple iCloud**: create an app-specific password at [account.apple.com](https://account.apple.com) under *Sign-In and Security → App-Specific Passwords*. Choose *Add Apple (iCloud) calendar*, then enter your Apple ID and that password and pick the calendars to show. Private calendars work, so you don't need to make anything public. The password goes into Windows Credential Manager, not into `config.toml`.
  Only calendars stored **in iCloud** come through. Calendars listed under *On My iPhone* exist only on the phone, so nothing else can read them. Turn on iCloud for Calendars (*Settings → your name → iCloud → Calendars*) and merge when asked, or move the events into an iCloud calendar.
- **Subscribed calendars, or any calendar link**: choose *Add a calendar link*. For an iPhone subscription, find the link under *Settings → Apps → Calendar → Calendar Accounts → Subscribed Calendars*; tap the calendar and copy its **Server** address.
- **Outlook / Microsoft 365, or any other ICS link**: use *Add a calendar link*, or add an entry like this to `config.toml`. Outlook's link is under *Settings → Calendar → Shared calendars → Publish a calendar*. A path to a local `.ics` file works in place of the URL.

  ```toml
  [[calendar.feeds]]
  name = "Work"          # optional
  url = "https://outlook.office365.com/owa/calendar/.../calendar.ics"
  color = "#f5a524"      # optional
  ```

The companion checks for new events every 10 minutes.

When Home doesn't show the *Up next* widget, a small dot on the sidebar's Calendar tab tells you there's still an event today. It takes the colour of that event's calendar (the first one the Calendar page lists) and goes away once the day's last event ends.

## Choosing pages

Home is always shown. To hide other pages, list the ones you want in `companion/config.toml`. The navigation bar shows them in the order you list them, after Home:

```toml
[pages]
enabled = ["home", "stats", "ai", "calendar", "weather", "media", "printer", "timer", "games", "network", "shortcuts"]
nav = "left"   # where the navigation bar goes: "left" (default), "right" or "bottom"
```

Remove a name to hide that page, or move it to move its tab. Without a `[pages]` block everything is shown except the 3D printer page, which turns on by itself once you add a printer, the Games page, which turns on when Steam is installed, and the GitHub page, which turns on when its widget is on Home. Add `"github"` to the list for the [GitHub page](#github-contributions). Without a list the tabs go in the order above, with Shortcuts last. Setup asks about each page too (the *Pages* step); it keeps your order and adds pages you turn on at the end. The companion sends the list to the board every time it connects, so restart the companion after editing. Changing `nav` restarts the board once so every page is laid out for the new space.

## When the PC sleeps

When Windows turns your monitor off, or the PC goes to sleep, the board follows it. Choose what it does in `companion/config.toml`:

```toml
[display]
pc_sleep = "off"   # "off" (default), "clock" or "none"
```

- `off`: the board's screen goes dark.
- `clock`: a dim clock with the date on black, moving to a new spot each minute.
- `none`: the board stays as it is.

Touch the board to bring it back for a minute; tap the clock to hide it. The board comes back by itself when the PC's screen wakes. Setup asks too (the *Screen sleep and night mode* step). Restart the companion after editing.

### Night mode

The board can also go dark on a schedule, whether the PC is on or not:

```toml
[display]
night = "23:00-07:00"   # leave empty for no night mode; "11pm-7am" works too
night_style = "clock"   # "off" (screen dark, default) or "clock"
```

The board keeps the schedule itself, so it still goes dark with the PC off. As with the PC sleeping, a touch brings it back for a minute. Setup asks for both (the *Screen sleep and night mode* step).

## Steam

The Games page shows the game you're playing, with its cover and how long this session has run, and your five most recent games. Tap a recent game to launch it. The Home widget `game` shows the same game in a small card.

Everything comes from Steam's local files on your PC: the registry (which game is running), the library manifests and your `localconfig.vdf` (recent games and playtime). Cover art comes from Steam's public image CDN, and the names of recent games you've uninstalled from the public Store API. Only the game's appid is sent, and both are cached in `~/.deskhub`. Launching opens `steam://rungameid/<appid>`, and only for games in the recent list. Steam only keeps total playtime in that file for some games, so the total shows when it's there and is left out otherwise.

**Friends and playtime (optional).** With your own Steam Web API key, the Games page also lists friends who are in a game, and shows total playtime for every game. Get a key at [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) (any domain name works), then run `uv run deskhub-setup` and add it in the Games step. Setup checks the key with Steam and keeps it in the Windows credential store (service `deskhub-steam`), not in `config.toml`. The companion then asks `api.steampowered.com` for your friends every minute and your playtime every 30 minutes, using your key and your Steam ID, which comes from Steam's local files. Your own **Friends List** must be set to Public in Steam (Profile > Edit Profile > Privacy Settings), or Steam refuses the friends list; playtime still works without it. Friends only show if their game details are public. Playtime shows as a small badge on each recent game's cover and on the Home widget.

To stop using the key, run setup again and choose not to keep it. To turn Steam off entirely, set `enabled = false` under `[steam]` in `config.toml`.

### Games that aren't on Steam

Popular games are recognised without any setup: League of Legends, Teamfight Tactics, VALORANT, Fortnite, Rocket League, Minecraft, Minecraft Bedrock, Roblox, Overwatch 2, World of Warcraft, Diablo IV, Hearthstone, StarCraft II, Call of Duty, Genshin Impact, Honkai: Star Rail, Zenless Zone Zero, Grand Theft Auto V, Apex Legends, EA SPORTS FC, The Sims 4, Halo Infinite, Escape from Tarkov, osu!. League of Legends and Teamfight Tactics run as the same program, so the companion asks the League client's local API, on your PC only, which one you're in. Riot, Epic and Battle.net games launch through their own launcher when you tap them, and games also sold on Steam get their Steam cover. To turn the built-in list off, set `enabled = false` under `[game_presets]` in `config.toml`, or skip some with `disabled = ["Roblox"]`. Your own `[[games]]` entry with the same name replaces a built-in one.

For anything else, such as emulators, modpacks or games from other launchers, start the game, then run:

```powershell
uv run deskhub-games
```

It lists the programs that have a window open, so you pick the game instead of looking it up. For Java games and other programs that run many things, it matches the window title; otherwise the program name. It then asks for an optional cover picture and what the board should open when you tap the game. `uv run deskhub-setup` offers the same step. To write the entry yourself, add a `[[games]]` block to `config.toml`:

```toml
[[games]]
name = "Minecraft"
process = "javaw.exe"          # the program's file name; a list works too
match = "minecraft"        # optional: text its command line must contain
image = "C:/Users/you/Pictures/minecraft.png"   # optional: a file or https URL
launch = "C:/XboxGames/Minecraft Launcher/Content/Minecraft.exe"   # optional
```

While that process runs, the board shows it as the game you're playing, with its session time. The companion remembers when you last played it and for how long (in `~/.deskhub/custom_games.json`), so it joins the recent games, and tapping it opens `launch`. Find the file name under **Details** in Task Manager. Java programs all run as `javaw.exe` or `java.exe` ("OpenJDK Platform binary" in Task Manager), so use `match` to tell them apart; Minecraft Bedrock is `Minecraft.Windows.exe`.

You can also match on the game's window title with `title`, which is handy for modpacks that all look like the same Java program. The game counts as running while a visible window's title contains that text. With `process` as well, the window must belong to one of those programs, so a browser tab with the same name doesn't count; `match` isn't used then. For example:

```toml
[[games]]
name = "GT: New Horizons"
title = "GT: New Horizons"
process = ["java.exe", "javaw.exe"]
```

Images can be any shape: they're cropped to fit. Without one the board shows a placeholder. A Steam game that's running takes priority, and custom games work with `[steam] enabled = false` or without Steam installed. Restart the companion after editing.

## Internet

The Stats page has two views, switched with **PC | Internet** at the top. The Internet view (and the `net` Home widget, which opens it) shows how your connection is doing. Turning off the `network` page in `[pages]` removes the Internet view and the switcher.

- **Status, latency, jitter and loss.** The companion probes every 2 seconds and keeps the last 60 samples for the chart. Latency is the median of the last five; jitter is how much it varies between probes; loss is the share of failed probes. The latency is a TCP connect to `1.1.1.1:443` (falling back to `8.8.8.8:443`), not an ICMP ping, so it needs no special rights and can read a few milliseconds higher than `ping`. You count as online while at least one of the last three probes succeeded.
- **Uptime and the last drop.** How long the connection has been up, and when it last went down and for how long.
- **Data used** today and this month, counted from your network adapters (all traffic on this PC, not only the internet). Totals are kept in `~/.deskhub/net_usage.json`.
- **Speed test.** Tap the button on the page to test download, upload and ping against `speed.cloudflare.com`. A test moves about 35 MB (25 MB down, 10 MB up), so it only runs when you tap it, or on a schedule if you set `speedtest_hours`. The last result is kept across restarts.
- **Public IP** is off by default. With `show_ip = true` it is asked from `speed.cloudflare.com` every 30 minutes and shown on the page.

```toml
[internet]
enabled = true
speedtest_hours = 0   # 0 = only when you tap the button; 6 = every 6 hours
show_ip = false
```

Live download and upload speeds come from the same numbers as the PC stats page.

## GitHub contributions

The `github` Home widget shows the green squares from your GitHub profile: one column per week, Sunday on top, the newest week on the right and today's square outlined. It shows as many weeks as fit: a 5-wide widget fits the whole year, narrower ones the most recent months.

- **One row tall:** the chart fills the height, with the year's total and your current streak beside it.
- **Two rows tall:** month labels over the chart, the year's total in the caption, and today, this week and the streak along the bottom.

The streak counts days in a row with contributions up to today; a quiet today doesn't break it until the day is over.

**The GitHub page** (tap the widget, or its tab) has more detail:

![GitHub page](docs/screenshots/github.png)

- **Last year:** the whole year's chart with month and weekday labels, and the total split into commits, pull requests, reviews and issues.
- **Streak:** the current streak, the longest one this year, and your busiest day.
- **This week:** contributions since Sunday and the change from last week, with a pair of bars per day (last week dim, this week green).
- **Top repos:** the four repositories with the most commits this year.

Add `"github"` to `[pages] enabled` to show it (setup offers to). Without a `[pages]` block it shows whenever the widget is on Home.

It needs a fine-grained personal access token with no extra permissions ([make one here](https://github.com/settings/personal-access-tokens/new)). Run `uv run deskhub-setup github`: it checks the token with GitHub, shows your total, keeps the token in the Windows credential store (not in `config.toml`) and offers to put the chart in the widest free spot on Home. Because the token is yours, private contributions count too when *Private contributions* is on in your profile settings.

**Private repositories.** With the token above, private work counts in the squares and the total, and the page shows how many contributions were private, but GitHub doesn't say which repositories they were in. To list private repositories under *Top repos*, give the token *Repository access: All repositories* (or pick some) with *Metadata* and *Contents* read-only. The companion then counts your commits on each one's default branch over the last year.

The companion asks GitHub's GraphQL API every 15 minutes, only while the widget or the page is on, and sends the board a new chart when something changed.

```toml
[github]
enabled = true
colors = "green"   # or "accent": shades of the board's amber
```

## Plex and Jellyfin

With a media server set up, the Media page splits in two: this PC on the left, the server on the right. The server card shows what plays anywhere (the TV, a phone, someone else's stream): the poster, the title, the show and episode (or the artist, or the movie's year), progress, and which device and user it plays for. With several streams going, the one playing wins and `(+2 more)` says how many others there are. `transcoding` appears next to the server's name when the server converts the stream. While nothing plays, the card says so and shows the server's library (`312 movies, 45 shows, 2,104 episodes`) and version. The Home media widget shows the PC, or the server's session while the PC is idle.

```powershell
uv run deskhub-setup media
```

Setup looks for servers on your network (both answer local discovery) and lets you type an address if yours doesn't answer. For **Plex** it opens the browser so you can approve the PC with your Plex account, or takes a token you paste. For **Jellyfin**, make an API key under *Dashboard → Administration → API Keys* and paste it. Either way setup checks the connection before it saves. Tokens and keys go in the Windows credential store; `config.toml` only gets the address:

```toml
[[media_servers]]
type = "jellyfin"          # or "plex"
name = "Jellyfin"
url = "http://192.168.1.20:8096"

[media]
server_users = ["alex"]    # optional: only these accounts' streams
```

The companion asks each server every 3 seconds while something plays and every 15 seconds otherwise. A server that doesn't answer is left alone for a minute. On **Jellyfin** the board's buttons pause, resume, skip and seek the session (when the player allows remote control). **Plex** is display-only: most Plex players don't take remote commands, so the board hides the buttons.

## Customizing Home

Home is a grid of 5 columns by 3 rows, under a slim bar with the time and date. Each widget takes a size in cells (width × height) and lays itself out for it. Place widgets in `companion/config.toml`, or use setup's *Home screen* step, which asks for a widget and a size and puts it in the first free spot (type `undo` to take the last one off, or `clear` to start over):

```toml
[home]
header = true
grid = [
  { widget = "weather", x = 0, y = 0, w = 3, h = 1 },
  { widget = "stats",   x = 0, y = 1, w = 3, h = 1 },
  { widget = "claude",  x = 0, y = 2, w = 3, h = 1 },
  { widget = "net",     x = 3, y = 0, w = 2, h = 1 },
  { widget = "events",  x = 3, y = 1, w = 2, h = 2 },
]
```

`x` and `y` count cells from the top left (0 to 4 across, 0 to 2 down).

| Widget | Shows | Sizes |
| --- | --- | --- |
| `weather` | current conditions and today's high and low; at 1 wide, the icon and temperature | 1 to 5 wide × 1 |
| `net` | Internet status, latency and the last speed test; at 1 wide, the latency | 1 to 5 × 1 |
| `claude` | Claude Code 5-hour and weekly limits; at 1 wide, the 5-hour limit | 1 to 5 × 1 |
| `stats` | CPU, GPU and RAM bars; at 1 wide, the numbers | 1 to 5 × 1 |
| `events` | your next calendar events, 1 to 3 depending on its height | 2 to 5 × 1 to 3 |
| `media` | now playing, with a play/pause button | 2 to 5 × 1 |
| `printer` | 3D print progress, time left and status | 2 to 5 × 1 |
| `game` | the Steam game you're playing (or your latest one), with its cover | 2 to 5 × 1 |
| `clock` | the big clock and date, for use without the top bar | 2 to 5 × 1 to 2 |
| `github` | your [GitHub contribution chart](#github-contributions); 5 wide shows the whole year | 2 to 5 × 1 to 2 |

How the grid behaves:

- **Cell size** comes from the space the navigation bar leaves: beside a side bar each cell is about 125 px wide, above a bottom bar about 145 px. Every widget lines up on the same cells.
- **Checks:** the companion leaves out (and logs) a widget that overlaps another, runs off the grid, or asks for a size it doesn't come in.
- **Hidden pages:** a widget whose page you've turned off in `[pages]` is skipped, and its cells stay empty.
- **Tapping a widget** opens its page (the clock widget has none). A Claude Code alert on a 1-wide `claude` card widens over its neighbours so the text fits.

Without a `grid`, the older two-column form still works and is converted for you: `left = [...]` becomes 3 cells wide and `right = [...]` 2 cells wide, one row per widget, with `events` taking the rest of its column. Without a `[home]` block you get Claude limits and Up next on the left, and weather, now playing and PC stats on the right (3D print instead of PC stats once you've added a printer). The board remembers the layout, so it looks right at boot even before the companion connects.

**The big clock instead of the top bar.** The top bar shows the time with AM/PM on the left and the full date on the right, in about 44 px. For a large clock instead, turn the bar off and place the `clock` widget, which scales its digits to its cells:

```toml
[home]
header = false
grid = [
  { widget = "clock",   x = 0, y = 0, w = 3, h = 2 },
  { widget = "weather", x = 3, y = 0, w = 2, h = 1 },
  { widget = "stats",   x = 3, y = 1, w = 2, h = 1 },
  { widget = "media",   x = 0, y = 2, w = 5, h = 1 },
]
```

## 3D printer

The printer page shows state, progress, time left, layer, temperatures, speed, errors and filament colours for up to 4 printers, in any mix of:

| Brand | Printers | How |
| --- | --- | --- |
| [Bambu Lab](#bambu-lab) | A1, A1 mini, P1P, P1S, X1C, X1E, H2D | MQTT, on your network or through Bambu's cloud |
| [Klipper (Moonraker)](#klipper-moonraker) | Voron, Sovol SV08, Qidi, Elegoo Neptune 4, Snapmaker U1, Creality K1/K2 with Moonraker, anything you run from Mainsail or Fluidd | Moonraker's HTTP API |
| [Prusa](#prusa-prusalink) | MK4/MK4S, MK3.9, MK3.5, XL, MINI/MINI+, CORE One | PrusaLink |
| [OctoPrint](#octoprint) | Any printer OctoPrint drives: older Creality Enders, Prusa MK3S, Anycubic i3 Mega... | OctoPrint's REST API |
| [Flashforge](#flashforge) | Adventurer 5M / 5M Pro, AD5X; Adventurer 3/4, Creator Pro, Finder | HTTP API (newer), G-code port (older) |
| [Elegoo](#elegoo-centauri-carbon) | Centauri Carbon | SDCP over WebSocket |
| [Snapmaker](#snapmaker-20) | Snapmaker 2.0 A150, A250, A350 | Touchscreen Wi-Fi API |
| [Snapmaker](#snapmaker-j1--artisan) | J1, J1s, Artisan | SACP, as Snapmaker Luban connects |
| [Anycubic](#anycubic-lan-mode) | Kobra 3 / 3 Max, Kobra S1 / S1 Max, Kobra 4, Kobra X, with ACE Pro | LAN Mode MQTT |
| [Creality](#creality) | K1 / K1C / K1 Max / K1 SE, K2 / K2 Plus / K2 Pro, Hi, Ender-3 V3 / V3 KE, with CFS | Creality Print's WebSocket |

Not supported yet: the Anycubic Kobra 2 series (no LAN Mode on stock firmware: the Kobra 2 Pro, Plus and Max only talk to Anycubic's cloud, and the Kobra 2 and Neo have no network; over USB they can go through OctoPrint) and older Creality printers without networking (Ender-3, Ender-3 V2, CR-10...), which can go through [OctoPrint](#octoprint). Printers on Klipper or OctoPrint work whatever the brand.

Setup offers a *3D printers* step. You can also run it on its own, pick the brand from the menu, then restart the companion:

```powershell
uv run deskhub-printers
```

Passwords, API keys, check codes and tokens go into Windows Credential Manager (under `deskhub-bambu` for Bambu, `deskhub-printers` for the rest), never into `config.toml`. Setup tests the connection before saving and tells you what it found. Everything except Bambu's cloud option needs the PC on the same network as the printer.

None of the brands below were tested on real printers by this project: each one was built from the maker's published API, or from open-source tools that talk to that printer. If something shows wrong, please open an issue with your printer model and firmware version.

### Bambu Lab

OrcaSlicer and Bambu Handy have no API of their own; they read the printer over MQTT, and so does the companion. Pick one way to connect per printer:

- **Cloud**: choose *Bambu Lab: add printers from a Bambu cloud account*, enter your Bambu email and password, and the emailed verification code if Bambu asks for one, then pick your printers. This works from anywhere, and OrcaSlicer and Bambu Handy keep working normally. Your password is not stored. Bambu's access token (valid about 3 months) goes into Windows Credential Manager under `deskhub-bambu`. When it expires the companion logs a line telling you to run `deskhub-printers` again. Use region `cn` only for China accounts.
- **Local (LAN)**: choose *Bambu Lab: add a printer on the local network* and enter:
  - **IP address**: on the printer, *Settings → WLAN* (or *Network*); or your router's device list.
  - **Serial number**: *Settings → Device* on the printer, or the label on its back or underside.
  - **Access code**: 8 characters on the printer, under *Settings → WLAN* or *LAN Only Mode*.

  Setup tests the connection for up to 10 seconds and tells you what it found. The access code is stored in Windows Credential Manager, not in `config.toml`. Newer firmware only lets third-party tools connect when **LAN Only Mode** or **Developer Mode** is turned on in the printer's settings (turning on LAN Only Mode disconnects the printer from Bambu's cloud). Your PC must be on the same network as the printer.

The cloud sign-in is reverse-engineered by the community, not documented by Bambu, so it can change without notice. The [ha-bambulab](https://github.com/greghesp/ha-bambulab) project tracks it.

A printer entry in `config.toml` looks like this:

```toml
[[printers]]
name = "P1S"
type = "local"          # or "cloud"
serial = "01P00A000000000"
host = "192.168.1.60"   # local only; cloud uses account = "you@example.com" and region = "us"
```

### Klipper (Moonraker)

Choose *Klipper (Moonraker)* and enter:

- **IP address or hostname**: the address you open Mainsail or Fluidd at, without `http://`.
- **Port**: Moonraker's own port is `7125`. If only Mainsail or Fluidd is reachable, use `80`.
- **API key**: usually left empty. Moonraker lets devices on your home network in when they match `trusted_clients` in `moonraker.conf`, which most printer images set up. Otherwise create a key in Mainsail or Fluidd's settings; it goes into Windows Credential Manager under `deskhub-printers`, not into `config.toml`.

Setup checks that Moonraker answers, suggests the printer's hostname as its name, and asks for a model to show on the board (`Klipper` if you leave it). The companion polls the printer every 2 seconds. Time left comes from the slicer's estimate when the file has one, and the layer count from `SET_PRINT_STATS_INFO` or the file's layer height. Filament colours are the ones the slicer wrote into the file; on a toolchanger the tool in use is highlighted. Speed is Klipper's speed factor, such as `100%`.

```toml
[[printers]]
name = "Voron"
type = "moonraker"
host = "192.168.1.70"
port = 7125             # optional, 7125 is the default
model = "Voron 2.4"     # optional, shown on the board
```

### Prusa (PrusaLink)

Turn on PrusaLink on the printer (*Settings → Network → PrusaLink*), then choose *Prusa (PrusaLink)* and enter the IP address, the user name (usually `maker`) and the password from that same screen. The companion signs in with HTTP Digest, so the password never crosses the network as plain text. Shows state, progress, time left, file, nozzle and bed temperatures and the print speed. PrusaLink doesn't report layers or filament colours, so those stay empty.

```toml
[[printers]]
name = "MK4"
type = "prusalink"
host = "192.168.1.71"
user = "maker"
model = "MK4S"
```

### OctoPrint

For any printer you run through OctoPrint (usually OctoPi on a Raspberry Pi). Create an API key under *OctoPrint Settings → Application Keys*, choose *OctoPrint* and enter the Pi's address, the port (`80` for OctoPi, `5000` if you run OctoPrint yourself) and the key. Layer numbers show if the *DisplayLayerProgress* plugin is installed. When OctoPrint isn't connected to the printer, the board shows it idle with a note saying so.

```toml
[[printers]]
name = "Ender 3"
type = "octoprint"
host = "octopi.local"
```

### Flashforge

- **Adventurer 5M / 5M Pro, AD5X**: enter the IP address, the serial number (on the *About* screen, starts with `SN`) and the check code from the printer's network settings, the same pair Orca-Flashforge asks for. Turn on LAN-only mode if the printer doesn't answer. The AD5X material station's colours show on the board.
- **Adventurer 3/4, Creator Pro, Finder and other older printers**: leave the serial number and check code empty. The companion then uses the G-code port (8899).

```toml
[[printers]]
name = "AD5X"
type = "flashforge"
host = "192.168.1.72"
serial = "SNMOMC9900000"
```

### Elegoo Centauri Carbon

Choose *Elegoo Centauri Carbon* and enter the printer's IP address (*Settings → Network* on the printer). Nothing else is needed: no password or access code, just the printer and the PC on the same network. Shows state, progress, layers, time left, file, nozzle, bed and chamber temperatures, the print speed and print errors. Levelling or homing outside a print shows as preparing, without the last job's details. The printer allows only a handful of connections at once (slicer, phone app, Home Assistant...); the companion uses one, so close one of the others if setup can't connect.

```toml
[[printers]]
name = "Centauri"
type = "elegoo"
host = "192.168.1.73"
```

Elegoo printers on Klipper (Neptune 4 series) go through [Moonraker](#klipper-moonraker) instead.

### Snapmaker 2.0

For the A150, A250 and A350. Turn on Wi-Fi on the touchscreen, choose *Snapmaker 2.0* and enter its IP address. While setup tests the connection, the touchscreen asks whether to allow it: tap **Yes** within a minute. The token it hands out goes into Windows Credential Manager. Laser and CNC jobs show their state and progress without temperatures. The Snapmaker U1 runs Klipper, so add it as a [Klipper printer](#klipper-moonraker).

### Snapmaker J1 / Artisan

For the J1, J1s and Artisan. On the touchscreen, turn on **Allow Remote Connection** in the settings, under *Remote Connection*, then choose *Snapmaker J1 / J1s / Artisan* and enter the printer's IP address. While setup tests the connection, the touchscreen asks whether to let this PC connect: tap **Connect** within a minute. The companion connects the way Snapmaker Luban does, on port 8888, and keeps the token it made in Windows Credential Manager. With *Remote Connection* set to *Only the first time*, the printer remembers it and doesn't ask again; set to *Always*, it asks each time the companion reconnects.

Shows state, file, the nozzle in use (left or right) and its temperature, bed temperature, the print speed and the printer's error messages. Progress and time left show only where the printer reports the job's line count, which current J1 firmware doesn't, so on a J1 they stay empty. Laser and CNC jobs on the Artisan show their state and file without temperatures, with progress on the same terms. Filament colours don't show: the printer doesn't report them over this connection.

The printer takes one remote connection at a time, so disconnect Luban (or close it) while the companion is connected, and the other way round. If the companion can't get an answer (Luban is connected, or an old prompt is still on the screen), it tries again after a minute, then less often. Tap **Refuse** on any prompt left on the touchscreen to clear it. Tapping **Disconnect** on the touchscreen ends the companion's connection too, and it stays away for 15 minutes before connecting again. Keep **Safe Mode** off: with it on, the touchscreen locks while anything is connected.

```toml
[[printers]]
name = "Snapmaker J1"
type = "snapmaker-sacp"
host = "192.168.1.75"
model = "J1"            # optional, shown on the board
```

### Anycubic (LAN Mode)

For the Kobra 3 / 3 Max, Kobra S1 / S1 Max, Kobra 4 and Kobra X on stock firmware. Turn on **LAN Mode** (*Settings → Network → LAN Mode*), choose *Anycubic (LAN Mode)* and enter the printer's IP address. No password: the companion asks the printer for its login each time it connects. ACE Pro slot colours show on the board, with the slot in use highlighted. LAN Mode takes the printer out of Anycubic's cloud and app until you pair it again.

### Creality

For the K1 / K1C / K1 Max / K1 SE, K2 / K2 Plus / K2 Pro, Hi and Ender-3 V3 / V3 KE on stock firmware. Choose *Creality (stock firmware)* and enter the printer's IP address (*Settings → Network* on the printer, or tap the connected Wi-Fi network). Nothing else is needed: no password, no root, no developer mode. The companion connects the way Creality Print does, on port 9999. Setup suggests the printer's host name as its name and reads the model. Shows state, progress, layers, time left, file, nozzle, bed and chamber temperatures, the print speed and print errors. On a printer with a CFS, the slot colours and materials show on the board, with the slot in use highlighted; the external spool holder follows the CFS slots. The start-of-print self-test shows as preparing.

```toml
[[printers]]
name = "K2 Pro"
type = "creality"
host = "192.168.1.74"
model = "K2 Pro"        # optional, shown on the board
```

A rooted K1 or a K2 with Moonraker turned on can also go through [Moonraker](#klipper-moonraker), but this way needs neither. The Sonic Pad isn't covered: nothing we found confirms it offers this connection.

## Claude Code usage

The AI page has two parts:

- **Plan limits**: your 5-hour and weekly usage percentages with reset times, on Pro and Max plans. Claude Code hands these to its [status line](https://code.claude.com/docs/en/statusline) command. To capture them, run this once in `companion/`:

  ```powershell
  uv run python install_claude.py statusline
  ```

  This backs up `~/.claude/settings.json` to `~/.deskhub/`, then points the status line at a small bridge script. The bridge saves the numbers for the companion, then runs whatever status line you had before, so your status line looks the same. `uv run python install_claude.py statusline --remove` puts your old setting back.

  Claude Code only reports limits to the status line of an interactive **terminal** session (`claude` in a terminal). The Claude desktop app and the IDE extensions use them without reporting them, so the percentages stay at the last terminal reading. Once a reading is more than 10 minutes old, the board shows "as of" with its time, on Home and the AI page, in place of the reset countdown. If you mostly use the desktop app, turn on live limits (below). Running `claude` in a terminal and sending one message refreshes them.

  Restart any Claude Code session that was already open, because only sessions started after the install report limits.

  **Live limits (optional).** To keep the percentages fresh no matter which Claude app you use, set this in `config.toml`. Setup asks about it too.

  ```toml
  [claude]
  live_limits = true
  ```

  The companion then asks Anthropic for your current limits every minute while you're using Claude Code, and every 5 minutes otherwise. It uses the sign-in that the `claude` CLI saved in `~/.claude/.credentials.json`. It sends no messages to Claude, so it uses no tokens or API credits. The sign-in token stays in memory: it isn't logged and isn't sent to the board. The Claude desktop app and IDE extensions don't renew that sign-in, so when it expires (every few hours) the companion runs `claude auth status`, which has Claude Code renew it the way it does on its own use. That sends no message, and the companion never touches the token itself. If renewing fails, live limits pause until the next time you use `claude`.

  The endpoint is undocumented, so Anthropic could change it. If that happens, the board falls back to status-line readings, which update after a session's first reply. When a 5-hour window expires, the board shows 0% and "Starts with next prompt" until your next prompt opens a new one.
- **Token totals**: tokens today, in the last hour, over the last 7 days and per model. The companion reads them from Claude Code's local session files in `~/.claude/projects/`, using only token counts, model names and timestamps. Claude Code says that file format can change between releases, so this part may need an update after a Claude Code update.

### Codex

If you use OpenAI Codex instead, the AI page shows its usage the same way. The companion reads token counts, model names and limits from Codex's local session logs in `~/.codex/sessions` (or `$CODEX_HOME`), never message text. Codex has no live limits feed, so the 5-hour and weekly percentages come from the last Codex reply and can be stale; Codex has no local 5-hour window estimate either. Choose the agent with `agent` in the `[ai]` section of `config.toml`: `"auto"` (the default) shows whichever agent you used most recently, or set `"claude"` or `"codex"`. `uv run deskhub-setup` asks for it too.

### Waiting alerts

When a Claude Code session needs a permission approval, asks you a question, has a plan ready, or has finished and is waiting for your reply, the board shows it in place of the usage card on Home and over the history chart on the AI page, with the project name and Claude Code's own message (such as "Claude needs your permission to use Bash"), and puts a dot on the AI tab. Amber means it needs a permission; periwinkle means it's waiting for a reply. Tap the open button (**Show on PC** on the AI page) to bring that session's window to the front, or the cross (**Not now**) to dismiss it. A finished session only alerts after it has waited 30 seconds (`idle_alert_seconds` under `[claude]`), so the board doesn't nag while you're still at the PC. Opening the Claude app (or the terminal running the session) counts as seeing a finished session, so it clears from the board by itself, and a session that finishes while that window is in front doesn't alert at all. Questions and permission requests stay until you answer them. If you installed the hooks before, run the install command again to pick up new ones.

![Waiting alert](docs/screenshots/alert.png)

Install the hooks once, in `companion/`:

```powershell
uv run python install_claude.py hooks
```

This copies a small `hook_bridge.py` to `~/.deskhub/` and appends hooks to `~/.claude/settings.json` (after backing it up). Your existing hooks are left alone. `uv run python install_claude.py hooks --remove` deletes only the ones it added, and `install_claude.py` on its own installs both the status line and the hooks. Restart sessions that were already open.

Privacy: the hooks store only the session state, the project folder name and Claude's notification text (like "Claude needs your permission to use Bash") in `~/.deskhub/claude_sessions/`. Prompts and tool input are never read or saved. It works for terminal and desktop-app sessions that load the hooks in `~/.claude/settings.json`. Turn it off with `alerts = false` under `[claude]` in `config.toml`.

## Shortcuts

To set up the buttons, run:

```powershell
uv run deskhub-setup shortcuts
```

It lists your buttons and lets you add, change, move or remove them. For each one it asks for a label, what it does (from the table below), the target, an icon (`?` lists them, and one is suggested for the action) and a colour. Key combinations are checked as you type them. Restart the companion afterwards to send the buttons to the board.

To edit them by hand instead: each `[[tiles]]` block in `companion/config.toml` is one button, in order. Up to 16 are allowed; 4, 6, 8, 12 or 16 make an even grid.

```toml
[[tiles]]
label = "Mute mic"
icon = "mic_off"
color = "#b4413c"
action = "mic"
```

| `action` | `target` |
| --- | --- |
| `keys` | a key combination, such as `ctrl+shift+m`, `win+shift+s` or `f13` |
| `run` | a program or command, such as `wt.exe` or `code C:\Code\project` |
| `open` | a file, folder or URL to open with its default app |
| `media` | `toggle`, `next` or `prev` |
| `volume` | `up`, `down` or `mute` |
| `lock` | locks the PC; leave `target` empty |
| `mic` | mutes or unmutes your default microphone in Windows; leave `target` empty |

Toggle tiles light up on the board while they're on: the mic tile while your microphone is muted, and the `volume` `mute` tile while your speakers are muted. The companion reads both from Windows every second, so they stay right when you mute from the taskbar or a headset button. A tile with a mic icon lights up for the microphone too, so an app's own mute hotkey (like `keys` `ctrl+shift+m`) only matches if that app also mutes the mic in Windows; use `action = "mic"` to be sure. Set `state = "mic_mute"` or `"speaker_mute"` to choose, or `state = ""` to keep a tile unlit.

`config.example.toml` lists every icon name. Restart the companion after editing.

The board's fonts only cover Latin letters. Accented letters in labels, event titles and song titles show without their accents (é becomes e), and text in other scripts, such as Japanese or Cyrillic, is dropped.

## Troubleshooting

- **Flashing won't start**: hold **BOOT**, tap **RESET**, let go of **BOOT**, and run setup again. Also try a different cable, since some only carry power.
- **The board never joins Wi-Fi**: check that the network is 2.4 GHz and that the password is right. Run `uv run deskhub-setup wifi` to change either.
- **The companion says "hub not reachable"**: your network may not resolve `deskhub.local`. Find the board's IP address in your router's list of devices, where it appears as `deskhub`, then run `uv run deskhub-setup hub` and enter it, or put it in `config.toml`:

  ```toml
  [hub]
  host = "192.168.1.50"
  ```
- **"python" opens the Microsoft Store, or ESP-IDF scripts fail**: Windows' built-in `python` alias is getting in the way. Setup works around it. If you run `idf.py` yourself, disable the alias under *Settings → Apps → Advanced app settings → App execution aliases*.
- **Errors mentioning "filename too long"**: clone the repo to a short path such as `C:\Code\deskhub`.
- **The board's host name**: in `firmware\`, load ESP-IDF as shown in [Run setup](#3-run-setup), then run `idf.py menuconfig`, open the **Desk Hub** menu, and run `idf.py -p COM5 flash`.

## How it works

The board runs a WebSocket server at `ws://deskhub.local/ws`. The companion connects, sends `{"type": "hello", "token": ...}`, and once the board answers `hello_ok` it streams JSON messages:

| From the PC | Contents |
| --- | --- |
| `stats` | `cpu`, `ram_used`/`ram_total` (GB), `gpu`, `gpu_temp`, `vram_used`/`vram_total`, `net_down`/`net_up` (KB/s), `disk` (%), CPU and GPU names. Sent every second. |
| `media` | `active`, `playing`, `title`, `artist`, `album`, `source`, `pos`/`dur` (seconds), `can_seek`, `art_id`, and `controls` (`false` hides the buttons). Sent every second. |
| `media_server` | `configured`, `name`, `kind` (`plex`/`jellyfin`), `online`, `version`, `library`, `streams`, `transcoding`, then the shown session in the same fields as `media` (`active` false while nothing plays). Sent every second when a server is set up; `configured: false` otherwise. |
| binary | `ART1`, then `u32 art_id`, `u16 width`, `u16 height` and the cover's RGB565 little-endian pixels. Sent when the cover changes. `ARS1` is the same for the media server's poster (2:3). |
| `events` | Up to 16 events with `title`, `loc`, `cal`, `start`/`end` (Unix time), `all_day`, `color`. |
| `tiles` | Up to 16 buttons with `label`, `icon`, `color`. |
| `layout` | `pages`, the page names to show; `nav` (`left`, `right` or `bottom`); `pc_sleep` (`off`, `clock` or `none`); `night_start`/`night_end` (minutes after midnight, -1 = no night mode) and `night_style` (`off` or `clock`). Sent right after `hello_ok`. |
| `home` | `header` (time and date in a top bar) and `grid`, a list of `widget`, `x`, `y`, `w`, `h`. Also `left` and `right` columns of widget names, which firmware from before the grid uses instead. Sent right after `layout`. |
| `pc_power` | `asleep`: whether the PC's screen is off or the PC is going to sleep. Sent after each connect and when it changes. |
| `alert` | A Claude Code session waiting for you: `id`, `kind` (`permission` or `input`), `agent`, `title`, `detail` and `project`; or `clear: true` when nothing is waiting. |
| `tile_state` | `on`, the indexes of toggle buttons that are on (mic muted, speakers muted). Sent when it changes. |
| `printer` | `printers` (up to 4) with `name`, `model`, `online`, `state`, `pct`, `remaining_min`, `layer`/`layers`, `file`, temperatures, `speed`, `error` and `ams`. Sent when something changes, and at least every 30 seconds. |
| `net` | `online`, `latency_ms`, `jitter_ms`, `loss_pct`, `hist` (last 60 probes in ms, -1 = lost), `up_since`, `last_drop`, `today_bytes`, `month_bytes`, `speed`, `testing` and `ip`. Sent every 2 seconds. |
| `steam` | `found`, `playing` (`appid`, `name`, `session_s`, `total_min`) and `recent` (up to 5 with `appid`, `name`, `last`, `total_min`). Sent when something changes, and at least every 60 seconds. |
| binary | `STM1`, then `u32 appid`, `u16 width`, `u16 height`, `u16 kind`, `u16 0` and RGB565 little-endian pixels. Kind 0 is the playing game's header (340x159), 1 a Home thumbnail (64x96, portrait), 2 a portrait cover (96x144). |
| `claude` | `limits`, the current 5-hour `block`, `today`, `last_hour`, `days` (7 values) and `models`. Sent every 5 seconds. |

| From the board | Contents |
| --- | --- |
| `media` | `cmd` (`toggle`, `next`, `prev` or `seek`) and `value` (seconds, for `seek`) |
| `media_server` | the same, for the server's session (Jellyfin) |
| `speedtest` | no fields; runs a speed test now (at most one per 2 minutes) |
| `steam_launch` | `appid`, a recent or running game to launch |
| `shortcut` | `id`, the button's index. The PC looks up what the button does, so the board never holds commands. |
| `alert_action` | `id` of the alert and `action`: `focus` (bring that session's window to the front) or `dismiss` |

The board also serves a few HTTP endpoints, all of which need the token as `?token=…`:

| Endpoint | What it does |
| --- | --- |
| `POST /firmware` | Takes a new firmware image. The board asks on screen before installing it (see [Updating the firmware](#updating-the-firmware)). |
| `GET /screenshot` | The current screen as a BMP. |
| `GET /tap?x=…&y=…` | Taps the screen at that point. |
| `GET /perf` | Rendering stats as JSON (frames per second, frame times). `&full=1` also times a full-screen redraw. |

The board treats the PC as offline once nothing has arrived for 5 seconds. Without the token, other devices on your network can't drive the display or trigger your shortcuts. The traffic is not encrypted, so use a network you trust.

## Development

```
firmware/    ESP-IDF 5.5 + LVGL 9 firmware for the ESP32-S3
companion/   Python companion: stats, media, calendars, Claude usage, shortcuts, setup
docs/        screenshots
.github/     CI: builds the firmware and runs the companion tests on every push
```

- **Build by hand**: in `firmware/`, load ESP-IDF's `export.ps1` (see [Run setup](#3-run-setup)), then run `idf.py build` and `idf.py -p COM5 flash monitor`. The board's settings live in `firmware/sdkconfig`, which holds your Wi-Fi password and is git-ignored.
- **Tests**: in `companion/`, `uv run python tests/run_all.py` runs every `tests/test_*.py` and lists any that fail; each one also runs on its own. The calendar test starts a local CalDAV server, the printer test uses a tiny local MQTT broker and needs no printer, and `test_setup.py` looks up cities on Open-Meteo, so it needs the internet.
- **Without the board**: `uv run python tests/fake_hub.py --seconds 10` speaks the board's side of the protocol and checks every message. In a second terminal, run `uv run python -m deskhub --config tests/test_config.toml`.
- **Debug endpoints**: `/screenshot`, `/tap` and `/perf` on the board; see [How it works](#how-it-works).

### Hardware notes (4.3B)

- RGB panel, 16-bit, 16 MHz pixel clock. HSYNC 46, VSYNC 3, DE 5, PCLK 7. Data: B 14/38/18/17/10, G 39/0/45/48/47/21, R 1/2/42/41/40.
- I²C on SDA 8 / SCL 9 is shared by the GT911 touch controller (0x5D) and a CH422G I/O expander. EXIO1 resets the touch controller, EXIO2 switches the backlight and EXIO3 resets the LCD.
- The backlight can only be switched on or off. There's no dimming.

## Roadmap

Planned features are listed in [ROADMAP.md](ROADMAP.md).

## License

[MIT](LICENSE). The bundled fonts keep their own licenses, which are listed below.

## Credits

- [LVGL](https://lvgl.io) (MIT) and [ESP-IDF](https://github.com/espressif/esp-idf) (Apache 2.0).
- [Inter](https://github.com/rsms/inter) (SIL OFL 1.1), with LVGL's built-in Montserrat as a fallback, and [Material Icons](https://github.com/google/material-design-icons) (Apache 2.0). See `firmware/main/fonts/`.
- Weather and city search by [Open-Meteo](https://open-meteo.com) (CC BY 4.0).
- The Claude logo is a trademark of Anthropic and is shown only to label Claude Code usage. `firmware/tools/make_logos.py` generates it from the SVG; other agents' logos can be added there.
- Inspired by [ClawPal](https://github.com/Kaayoos/ClawPal). No ClawPal code is used.
