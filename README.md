<div align="center">

# DisplayGuard

**Stop fullscreen games from wrecking your multi-monitor layout.**

When you launch or quit a fullscreen game, Windows often shuffles your monitor
arrangement — windows jump to the wrong screen, displays swap positions, your
carefully arranged desktop is gone. DisplayGuard detects that change and snaps
everything back automatically.

[Download](../../releases) · [How it works](#how-it-works) · [Build from source](#build-from-source)

</div>

---

## Why

If you game on more than one monitor, you've seen it: a fullscreen title
(especially exclusive-fullscreen ones) triggers a display-mode change, and
Windows rearranges your monitors. Every window you had open scatters. You fix it
by hand, every single time.

DisplayGuard runs quietly in the system tray, watches for these layout changes,
and restores your saved arrangement within a couple of seconds — no manual
re-dragging.

**It never touches the game.** DisplayGuard works entirely at the Windows
display/system level — no memory injection, no overlay, nothing that an
anti-cheat could flag. Your account stays safe.

## Features

- 🟢 **Automatic restore** — listens for `WM_DISPLAYCHANGE` and restores your saved monitor layout
- 🖥️ **Simple GUI** — monitor list, live activity log, one-click manual controls
- 🔔 **System tray** — keeps running when you close the window; click the tray icon to reopen
- 💾 **Persistent profile** — your reference layout is saved to JSON and survives restarts
- 🔒 **Single instance** — won't launch twice by accident
- 🪶 **Lightweight** — pure `ctypes` Windows API calls, no heavyweight dependencies

## Download

Grab the latest installer from the [**Releases**](../../releases) page:
`DisplayGuard-Setup-x.y.z.exe`. No Python required.

The installer is **per-user** (no admin/UAC prompt), and offers to start
DisplayGuard automatically with Windows.

> **SmartScreen note:** until the binary builds up download reputation, Windows
> SmartScreen may show a warning on first run. Click **More info → Run anyway**.
> This is expected for new independent software.

## Usage

1. Run **DisplayGuard** (it starts minimized to the tray).
2. Arrange your monitors the way you like, then click **Save current layout**.
3. Play your game. If Windows changes the arrangement, DisplayGuard restores it
   automatically a couple seconds later.

### Tray menu

| Item | What it does |
|------|--------------|
| Open window | Show the main window |
| Save current layout | Capture the current monitor positions as the reference |
| Disable / Enable protection | Pause or resume automatic restore |
| Exit | Quit completely |

## How it works

DisplayGuard creates a hidden message-only window and receives the Windows
`WM_DISPLAYCHANGE` notification whenever the display configuration changes. After
a short delay (default 2 seconds, to let the game finish its mode switch) it
compares the current layout against the saved one and, if they differ, calls
`ChangeDisplaySettingsEx` to restore each monitor's position, resolution,
refresh rate, and orientation.

## Build from source

### Requirements

- Python 3.8+
- [PyInstaller](https://pyinstaller.org/), `pystray`, `Pillow`
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (only needed to build the installer)

### Run directly

```powershell
pip install -r requirements.txt
python display_guard.py
```

### Build the installer

The full pipeline (clean → PyInstaller → optional code-signing → Inno Setup) is
wrapped in `build.ps1`:

```powershell
.\build.ps1 -Version 1.0.0                            # unsigned
.\build.ps1 -Version 1.0.0 -CertThumbprint "<thumb>"  # signed with an OV cert
```

The result is `Output\DisplayGuard-Setup-<version>.exe`.

### Build pipeline files

```
display_guard.py     # application source
DisplayGuard.spec    # PyInstaller config (onedir, console=False, UPX off)
version_info.txt     # exe version resource
installer.iss        # Inno Setup 6 script (per-user, EN+KR, startup option)
build.ps1            # one-shot build script
icon.ico             # application icon (auto-generated if missing)
requirements.txt     # Python dependencies
```

## Feedback wanted

DisplayGuard is early and I'd genuinely like to know whether it fixes the problem
on **your** setup — especially edge cases I can't test alone: mixed refresh rates,
portrait monitors, HDR, and fractional display scaling (DPI).

- 🐞 Something broken or the layout not restored right? → [open a bug report](../../issues/new?template=bug_report.yml)
- 💡 Idea or feature request? → [tell me here](../../issues/new?template=feature_request.yml)

## Known limitations

- Windows only (uses the Windows display API directly).
- The first build is **unsigned**, so SmartScreen warns on first run (see above).
- Restores monitor **position, resolution, refresh rate, and orientation**; it does
  not currently manage HDR state or per-game profiles (planned — see roadmap).

## Roadmap

DisplayGuard is free and solves the core problem completely. A **Pro** version
(one-time purchase, not a subscription) is planned with per-game profiles and
automatic switching, resolution/refresh/HDR/primary-display capture, and cloud
profile sync. The free version will always cover the essential layout
protection.

## License

[MIT](LICENSE)
