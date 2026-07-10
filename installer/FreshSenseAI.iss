#define MyAppName "FreshSense AI"
#define MyAppVersion "0.1.0"
#define MyAppExeName "FreshSenseAI.exe"

[Setup]
AppId={{B6DEEA48-6B53-4B16-A6A8-E14FBF933A8A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\FreshSense AI
DefaultGroupName=FreshSense AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\outputs
OutputBaseFilename=FreshSenseAI-Setup-0.1.0
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\FreshSenseAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FreshSense AI"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\FreshSense AI"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch FreshSense AI"; Flags: nowait postinstall skipifsilent
