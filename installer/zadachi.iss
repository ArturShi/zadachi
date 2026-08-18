; Установщик приложения «Задачи» для Windows (Inno Setup 6).
; Собирается в GitHub Actions (см. .github/workflows/windows-build.yml)
; из папки dist\Zadachi, созданной PyInstaller'ом.

#define MyAppName "Задачи"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Zadachi"
#define MyAppExeName "Zadachi.exe"
#define MyAppId "8A2F6C41-9B3D-4E5A-9C1F-2D7E4B8A0F63"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Задачи
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
OutputDir=output
OutputBaseFilename=Zadachi-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardResizable=yes
PrivilegesRequired=lowest
SetupIconFile=zadachi.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
ArchitecturesAllowed=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "{cm:TaskAutostart}"; Flags: unchecked
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "..\dist\Zadachi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; Автозапуск при входе в Windows (только для текущего пользователя)
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "Zadachi"; ValueData: """{app}\{#MyAppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: autostart

[CustomMessages]
TaskAutostart=Запускать при входе в Windows
