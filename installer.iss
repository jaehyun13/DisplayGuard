#define MyAppName      "Spectra Display Studio"
#define MyAppVersion   "2.0.0"
#define MyAppPublisher "Spectra Display Studio"
#define MyAppExeName   "SpectraDisplayStudio.exe"
#define MyRunValue     "SpectraDisplayStudio"
; Same AppId as DisplayGuard 1.x, so this installer upgrades those installs in place.
#define MyAppId        "{{A7F3C2D1-8B4E-4F6A-9C2D-3E5F7A1B8D4C}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/jaehyun13/DisplayGuard
AppSupportURL=https://github.com/jaehyun13/DisplayGuard/issues
AppUpdatesURL=https://github.com/jaehyun13/DisplayGuard/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Per-user install (no UAC)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=SpectraDisplayStudio-Setup-{#MyAppVersion}
SetupIconFile=icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Detect a running copy (current name, or DisplayGuard 1.x) so setup asks the user
; to close it instead of failing to replace files that are in use.
AppMutex=Global\SpectraDisplayStudio,Global\DisplayGuard_v2
; Windows 10 1903+ required
MinVersion=10.0.18362
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoDescription=Spectra Display Studio Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "korean";  MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "startup";    Description: "{cm:AutoStartProgram,{#MyAppName}}"; GroupDescription: "Windows Startup:"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}";            GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Leftovers from DisplayGuard 1.x (the program file was renamed).
Type: files; Name: "{app}\DisplayGuard.exe"
Type: files; Name: "{group}\DisplayGuard.lnk"
Type: files; Name: "{group}\Uninstall DisplayGuard.lnk"

[Files]
Source: "dist\SpectraDisplayStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";       Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyRunValue}"; \
  ValueData: """{app}\{#MyAppExeName}"" --minimized"; \
  Flags: uninsdeletevalue; Tasks: startup

[Run]
; Remove the DisplayGuard 1.x autostart entry (it points at the old program file).
Filename: "reg"; Parameters: "delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v ""DisplayGuard"" /f"; Flags: runhidden
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/f /im {#MyAppExeName}"; Flags: runhidden; RunOnceId: "KillApp"
; The app can also enable "Start with Windows" itself; remove that entry too.
Filename: "reg"; Parameters: "delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v ""{#MyRunValue}"" /f"; Flags: runhidden; RunOnceId: "DelRunKey"
