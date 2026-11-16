#define MyAppName      "DisplayGuard"
#define MyAppVersion   "1.1.1"
#define MyAppPublisher "DisplayGuard"
#define MyAppExeName   "DisplayGuard.exe"
#define MyAppId        "{{A7F3C2D1-8B4E-4F6A-9C2D-3E5F7A1B8D4C}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/displayguard/displayguard
AppSupportURL=https://github.com/displayguard/displayguard/issues
AppUpdatesURL=https://github.com/displayguard/displayguard/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Per-user install (no UAC)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=DisplayGuard-Setup-{#MyAppVersion}
SetupIconFile=icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Detect a running DisplayGuard (same mutex name the app creates) so setup asks
; the user to close it instead of failing to replace files that are in use.
AppMutex=Global\DisplayGuard_v2
; Windows 10 1903+ required
MinVersion=10.0.18362
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoDescription=DisplayGuard Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "korean";  MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "startup";    Description: "{cm:AutoStartProgram,{#MyAppName}}"; GroupDescription: "Windows Startup:"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}";            GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\DisplayGuard\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";       Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyAppName}"; \
  ValueData: """{app}\{#MyAppExeName}"" --minimized"; \
  Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/f /im {#MyAppExeName}"; Flags: runhidden; RunOnceId: "KillApp"
; The app can also enable "Start with Windows" itself; remove that entry too.
Filename: "reg"; Parameters: "delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v ""{#MyAppName}"" /f"; Flags: runhidden; RunOnceId: "DelRunKey"
