# DisplayGuard v1.0.0

**Stop fullscreen games from wrecking your multi-monitor layout.**

First public release. DisplayGuard runs in your system tray, detects when
Windows rearranges your monitors (which fullscreen games love to trigger), and
restores your saved layout automatically within a couple of seconds.

## Highlights

- 🟢 Automatic layout restore on `WM_DISPLAYCHANGE`
- 🖥️ Simple GUI with live monitor list and activity log
- 🔔 Runs quietly in the system tray
- 💾 Saved profile survives restarts
- 🪶 Lightweight — pure Windows API via `ctypes`, no game injection or overlay
  (anti-cheat safe)

## Install

1. Download **`DisplayGuard-Setup-1.0.0.exe`** below.
2. Run it — per-user install, **no admin prompt**. Optionally let it start with Windows.
3. Arrange your monitors, click **Save current layout**, and you're set.

> **SmartScreen:** as a brand-new independent binary, Windows SmartScreen may
> warn on first run. Click **More info → Run anyway**. Reputation builds over time.

## Requirements

- Windows 10 (1903+) or Windows 11, 64-bit

## Verified

Built and smoke-tested on Windows 11: silent install, per-user registration,
startup entry, single-instance launch, and correct detection of a 4-monitor
setup (mixed 60/144/165/240 Hz, including a 4K display).

---

**SHA-256** (`DisplayGuard-Setup-1.0.0.exe`):
`1D34526BA971BC112C895E868FCED38D0B7A3C3227F037CBEE76ED6EB0185AEB`

> Note: this build is currently **unsigned**. Code signing (SignPath Foundation
> for OSS, or a Sectigo OV cert) is planned for a future release.
