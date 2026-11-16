# DisplayGuard v1.1.1

**Simpler window, sturdier core.**

## What's new

- 🎨 **Redesigned window** — a single on/off switch, a visual map of your saved
  monitor layout, and a badge that tells you at a glance whether the current
  layout matches the saved one. The activity log is tucked away until you want it.
- 🚀 **Start with Windows** checkbox right in the window. Auto-started copies go
  straight to the tray instead of popping the window open at every login.
- 🌐 **Language picker in the window** (it is still in the tray menu too).

## Fixes

- Refresh-rate, orientation and primary-display changes are now detected and
  restored (previously only position/resolution changes triggered a restore).
- No more endless restore loop when a layout can't be applied (e.g. a monitor is
  unplugged): DisplayGuard pauses after 3 attempts until the next change.
- Turning protection off now also cancels a restore that was already pending.
- The "already running" check is reliable now, and 64-bit Windows API calls no
  longer risk truncated handles.
- The app starts even if its folder is read-only (settings and log fall back to
  `%LOCALAPPDATA%\DisplayGuard`), and a damaged settings file is ignored instead
  of breaking restore. Settings are written atomically; the log file is capped.
- The installer detects a running DisplayGuard before upgrading, and uninstall
  removes the "Start with Windows" entry.

## Requirements

- Windows 10 (1903+) or Windows 11, 64-bit

## Upgrading

Just run the new installer — it upgrades in place and keeps your saved layout.
