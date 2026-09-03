; TomoDesk installer (Inno Setup).
; Se compila desde build/build_windows.ps1, que sustituye la version en timepo
; de compilacion:  iscc.exe /DAppVersion=1.0.0 /DAppName=TomoDesk build\tomodesk.iss
;
; Nota: la instalacion copia el one-folder completo de dist\TomoDesk\ a {app}.
; La config, la base de datos y los logs se generan en %APPDATA%\TomoDesk y
; %LOCALAPPDATA%\TomoDesk en el primer arranque (rutas de usuario), por lo que
; la desinstalacion no borra datos personales.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppName
  #define AppName "TomoDesk"
#endif

#define AppPublisher "HaroldESC"
#define AppExeName AppName + ".exe"

[Setup]
AppId={{4F6E6D22-8A2B-4F0E-9D1C-3B7A5E2C8A91}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
SetupIconFile=assets\tomodesk.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\TomoDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent