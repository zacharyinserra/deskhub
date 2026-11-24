# Roadmap

Ideas for Desk Hub, roughly in order of value. Each item notes how it would work.

## Integrations

- [ ] **Phone notifications and text messages.**
  - **Approach:** read phone notifications through Windows rather than talking to the phone directly. Windows' Phone Link already mirrors texts and app notifications from Android phones and iPhones into Windows notifications. The companion reads them with the `UserNotificationListener` API (Windows asks the user for permission once), and could show other PC notifications too, such as Discord or Teams.
  - **On the board:** a Messages page plus a small Home widget with the latest few texts (sender, a preview and the time), and a brief pop-up when a new one arrives.
  - **Privacy:** off by default. Options to show the sender only, to hide previews, and to pick which apps count. Message text only goes to the paired board over the LAN and isn't stored.
  - **Limits:** replying from the board isn't possible with this approach. Phone Link has no supported way for other apps to send messages, so replies stay on the phone or in Phone Link. iPhone support in Phone Link is more limited than Android.
  - **Alternative for Android:** the open KDE Connect protocol could give the companion texts, battery level and "find my phone" directly, without Phone Link. It's more work and Android-only.

- [ ] **Media server extras.** A "Recently added" list on the Media page's server card while nothing plays. Plex controls for players that allow remote control.

- [ ] **Home Assistant.**
  - **Approach:** the companion talks to Home Assistant's REST and WebSocket APIs with a long-lived access token (kept in the Windows credential store), so state changes arrive at once instead of by polling.
  - **On the board:** shortcut tiles that can be lights, scenes, switches and scripts, lit while they're on. A Home page or widget with chosen sensors (temperatures, doors, power use). A camera snapshot pops up when the doorbell rings.

- [ ] **Discord voice.** Who's in your voice channel, with a ring around whoever is talking, plus Mute and Deafen buttons. Uses the Discord desktop app's local RPC connection, which needs a Discord application ID and a one-time approval in Discord.

- [ ] **GitHub extras.**
  - Refresh the contribution chart soon after a `git push` from this PC instead of waiting up to 15 minutes.
  - Actions runs in progress for your repositories with pass/fail, and pull requests waiting for your review, on the GitHub page and as a small Home widget. A pop-up when a run you started fails.

- [ ] **Transit departures.** The next buses and trains from chosen stops, with live delays, from the agency's GTFS-realtime feed (many publish one; some need a free key). A Home widget with the next two departures and "leave in 4 min".

- [ ] **Sports scores.** Live scores and upcoming games for chosen teams, from a free sports API such as ESPN's public scoreboard endpoints or TheSportsDB. A pop-up when one of your teams scores.

- [ ] **Package tracking.** Deliveries on their way with the carrier, status and expected day, through a tracking service such as 17TRACK (carrier APIs are each different and mostly need business accounts). Numbers added in setup or found in a forwarded email folder.

- [ ] **Homelab status.** Docker containers (running, stopped, unhealthy) from the Docker API, checks from Uptime Kuma, and load on the Plex or Jellyfin server. A sidebar dot when something is down.

- [ ] **Flight tracker.**
  - **Overhead:** planes near home, from ADS-B data. The companion polls a free feed such as adsb.lol or OpenSky for a box around the configured location, or reads a local receiver (readsb/dump1090 on a Raspberry Pi with an RTL-SDR stick) when one is set up. Flight number, airline, aircraft type, altitude, speed, heading and distance, with route (origin → destination) looked up by callsign.
  - **Following a flight:** enter a flight number (in setup, or from a calendar event that has one) to follow it from gate to gate: departure and arrival times with delays, a progress bar along the route and time to landing. Handy for picking someone up.
  - **On the board:** a Flights page with a small radar-style map of nearby planes and a list sorted by distance, and a Home widget with the closest plane or the flight being followed. A brief pop-up when a plane passes close overhead, with a configurable radius and altitude.
  - **Limits:** free feeds are rate-limited, so polling slows down when the page isn't shown. Route lookups for small or private aircraft are often missing. Delay and gate data for followed flights needs an API key from a flight-status service (AeroDataBox or similar).

## Day-to-day polish

- [ ] **Volume mixer.** A slider and mute button for each app making sound (game, Discord, Spotify, browser), and a switch between output devices such as headphones and speakers. The companion uses the Windows audio session API (pycaw) and changes the default device through the policy config interface. Could be a page of its own or part of Media.

- [ ] **"On air" light.** When any app is using the camera or microphone (Windows records this under `CapabilityAccessManager\ConsentStore`), the board shows a red ON AIR bar with the app's name, or turns fully red as a sign for the room. Optionally turns on Windows Do Not Disturb for the call.

- [ ] **Frame rate while gaming.** FPS, 1% lows and frame time on the Stats page and the Games widget while a game runs, from PresentMon (Intel's open tool, which works with any GPU).

- [ ] **Weather extras.** Air quality, pollen and UV on the Weather page (Open-Meteo has all three for free), and severe weather alerts as a pop-up and a sidebar dot.

- [ ] **Lyrics on the Media page.** Lines timed to the song that's playing, from LRCLIB (free, no key), with the current line highlighted. Plain lyrics when timed ones aren't available.

- [ ] **Break reminders.** A nudge to stand up or drink water after a set time at the PC, measured from keyboard and mouse activity (`GetLastInputInfo`), so time away resets it. Snooze or Done on the board.

- [ ] **Pomodoro on the Timer page.** Focus and break cycles (25/5 by default, with a longer break every fourth), a count of focus sessions today, and Windows Focus turned on and off with them.

## Done

- [x] Settings page in the browser (tray > Settings, `deskhub-config`): Home layout by drag and drop on an 800 × 480 preview, pages, shortcut tiles, screen and night mode, Wi-Fi, city and units with Build and flash, calendars, printers, games, AI, internet and GitHub; layout changes reach the board on save
- [x] Sidebar navigation, configurable pages and Home widgets, slim top bar
- [x] PC stats, media, weather, Google/Apple/ICS calendars, shortcuts
- [x] Claude Code usage with live limits, the Claude logo on Home and in the sidebar
- [x] Bambu Lab printers (cloud and local), including dual-nozzle models
- [x] One-command setup (`deskhub-setup`), public README with screenshots, MIT license
- [x] Claude Code "waiting for you" alert on the Home usage card and the AI page, with Show on PC and Not now
- [x] Codex usage on the AI page and Home, with the agent picked automatically and its own logo
- [x] Timer page: presets, countdown ring, pause and reset, a "Time's up" card, and the time left on its sidebar tab
- [x] Shortcut tiles that light up for mic and speaker mute, plus a `mic` action that mutes the microphone in Windows
- [x] Steam: a Games page and Home widget with the game being played, its cover and session time, and the last 5 games to launch with a tap
- [x] Steam extras with your own Web API key: friends in game and total playtime for every game
- [x] Internet stats: a Network page and Home widget with latency, jitter, loss, outages, data used and a Cloudflare speed test
- [x] The board sleeps with the PC: when Windows turns the monitor off, the board goes dark or shows a clock screensaver
- [x] Graphite design: flat near-black cards, an amber accent, cool data colours and the Inter font, on every page
- [x] Calendar dot on the sidebar: an event still to come today, in its calendar's colour, when Home doesn't show Up next
- [x] Readable scrolling: text that doesn't fit rests, eases slowly to its end, rests and comes back, everywhere text can overflow
- [x] Night mode: the board goes dark or shows a clock on a schedule kept on the board, and a touch wakes it for a minute
- [x] Plex and Jellyfin: the Media page splits into this PC (left) and the server (right), with the server's session (poster, progress, device and user) or its library and version while nothing plays; Jellyfin sessions can be paused, skipped and seeked from the board
- [x] Start with Windows: `deskhub-install` adds a hidden login shortcut (and `--remove` takes it away), offered as setup's last step
- [x] Tray icon for the companion: connection status, Edit config, Run setup, Restart, Open log and Quit; the login shortcut starts it with the icon
- [x] Firmware updates over Wi-Fi: `deskhub-flash` (and setup) send new builds to the board, which asks Install / Deny and rolls back a build that can't start; USB as the fallback
- [x] Home as a 5 × 3 grid: widgets placed by cell with sizes they support, checked by the companion; setup places them for you
- [x] GitHub repository with CI: the firmware builds with ESP-IDF 5.5 and the companion tests run on Windows
- [x] GitHub contribution chart: a Home widget with the last year of contributions, today outlined, the total and the streak, set up with `deskhub-setup github`
- [x] GitHub page: the year's chart with labels, contributions by kind, current and longest streak, this week vs last by day, and top repositories
