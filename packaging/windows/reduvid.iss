; SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
; Copyright (C) 2026 Catlinux
;
; Build with ISCC.exe reduvid.iss /DMyAppVersion=<version>

#ifndef MyAppVersion
#error MyAppVersion is required. Pass /DMyAppVersion=X.Y.Z to ISCC.
#endif

#define MyAppName "Reduvid"
#define MyAppPublisher "Catlinux"
#define MyAppURL "https://github.com/catlinux/Reduvid"
#define MyAppExeName "Reduvid.exe"

[Setup]
AppId={{75FBF937-788D-4E7E-A4AC-E15DAAAED704}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\windows
OutputBaseFilename=Reduvid-Setup-{#MyAppVersion}
SetupIconFile=..\..\src\reduvid\resources\icon\reduvid.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Per-user install (no UAC): with PrivilegesRequired=lowest, {autopf} maps to
; {localappdata}\Programs, so automatic updates never request administrator rights.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
english.LaunchProgram=Launch Reduvid
spanish.LaunchProgram=Iniciar Reduvid

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\windows\Reduvid\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram}"; Flags: nowait postinstall skipifsilent
; An update started from Reduvid ("Install now") passes /relaunch=1 so the app opens again.
Filename: "{app}\{#MyAppExeName}"; Flags: nowait runasoriginaluser; Check: RelaunchRequested

[Code]
function RelaunchRequested: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;
