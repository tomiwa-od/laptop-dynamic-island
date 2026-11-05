# Dynamic Island for Windows (v2)

A floating, clickable "Dynamic Island" pinned to the top of your screen.

- **Collapsed (notch):** time + a status glyph (music note when something's playing, else battery %).
- **Expanded:** Now Playing (Spotify/any media) with prev/play/next, a Quick Apps launcher, a Quick Notes pad, and clock/date/battery/CPU/RAM.

## Run

- **First time / setup:** double-click **run.bat**. It installs the dependencies
  (and the media package) and launches with a console window you can read logs in.
- **Everyday use (no black window):** double-click **start-island.vbs**. It runs
  the island silently via `pythonw`, detached — nothing to keep open.
- **Start automatically at login:** run **autostart-on.bat** once. Undo with
  **autostart-off.bat**.

## Controls

| Action | What it does |
|---|---|
| Hover | Expands while the mouse is over it |
| Click the notch | Pins it open so you can click things (click again to unpin) |
| Drag | Move it anywhere — the position is remembered |
| Right-click | Menu: Reset position, Quit |
| Esc | Collapse (or quit if already collapsed) |

## Quick Apps — make them yours

On first run a **config.json** appears next to the app. Edit the `quick_apps`
list to add/remove launchers. Each entry:

```json
{ "label": "Spotify", "icon": "🎵", "type": "uri", "target": "spotify:" }
```

- `type: "uri"`  → a Windows protocol link. Examples: `spotify:`, `ms-clock:`,
  `microsoft.windows.camera:`, `ms-settings:`, `mailto:`, `https://...`
- `type: "exe"`  → a program to run. Examples: `calc`, `notepad`, `mspaint`,
  or a full path like `C:\\Tools\\thing.exe`
- `type: "notes"` → opens the built-in Quick Notes pad
- `icon` is any emoji/character shown on the button.

## Media controls (Spotify etc.)

These use Windows' media transport, via the **winrt-Windows.Media.Control**
package (run.bat installs it automatically; it has Python 3.14 wheels). If it's
missing, the island still runs — the Now Playing row tells you the exact command
to install it. Manual install: `py -m pip install winrt-Windows.Media.Control`

## Appearance

In `config.json` under `appearance`:
- `blur` — frosted acrylic so the wallpaper shows through (set `false` for a
  solid look if your PC renders it oddly).
- `fill_opacity` — 0.0–1.0, how see-through the panel is (default 0.82).
- `accent_from_art` — tint the panel + play button using the album cover's colour.

## Updates

The app can update itself — see **PUBLISHING.md**. Set `update.url` in
`config.json` to your hosted `latest.json` and new releases install automatically.

## Roadmap

- Alarms/reminders created from the island (currently opens the Clock app).
- Notification pop-ins.
