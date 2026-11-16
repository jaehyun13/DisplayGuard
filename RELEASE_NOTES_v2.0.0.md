# Spectra Display Studio v2.0.0

**DisplayGuard grows into a display studio — and gets a new name.**

Layout protection (restoring your monitor arrangement after a fullscreen game
shuffles it) is still at the core. Around it there is now a full window for
managing a multi-monitor setup.

## What's new

- 🖥️ **Arrangement** — drag monitors into place with edge snap, choose the main
  display, rotate, and save named layout profiles you can switch between.
- ⚡ **Resolution & refresh rate** — pick any mode the driver offers; a 15-second
  countdown reverts automatically if the picture is wrong.
- 🎨 **Colour & HDR** — per-monitor RGB gain, gamma, brightness and contrast, the
  monitor's own brightness over DDC/CI, and the Windows HDR switch.
- 🪟 **Window zones** — per-monitor zone layouts, `Win+Alt+←/→/↑` hotkeys, and
  Shift+drop snapping.
- 📈 **Hardware & GPU** — display link details, exportable report, and live
  read-only GPU sensors (NVIDIA).
- 🚀 **Start with Windows** switch in Settings; auto-started copies stay in the tray.

## Protection fixes

- Refresh-rate, orientation and main-display changes are now detected and restored.
- No more endless restore loop when a layout cannot be applied (e.g. a monitor is
  unplugged): it pauses after 3 attempts until the next change.
- Turning protection off also cancels a restore that was already pending.
- Reliable "already running" check and 64-bit-safe Windows API calls.
- Starts even if its folder is read-only; a damaged settings file is ignored
  instead of breaking restore; settings are written atomically; the log is capped.

## Upgrading from DisplayGuard 1.x

Run the new installer — it upgrades in place, keeps your saved layout and
settings, and replaces the old autostart entry.

## Requirements

- Windows 10 (1903+) or Windows 11, 64-bit
- Microsoft Edge or Chrome for the app window (Edge ships with Windows)

> Note: this build is **unsigned**; SmartScreen may warn on first run.
