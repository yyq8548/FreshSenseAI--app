#ifndef MyAppName
  #define MyAppName "FreshSense AI"
#endif
#define MyAppPublisher "Yeqiao Yu"
#define MyAppURL "https://github.com/yyq8548/FreshSenseAI--app"
#define MyAppExeName "FreshSenseAI.exe"
#ifndef MyAppId
  #define MyAppId "{{B6DEEA48-6B53-4B16-A6A8-E14FBF933A8A}"
#endif
#ifndef MyOutputBaseFilename
  #define MyOutputBaseFilename "FreshSenseAI-Setup-" + MyAppVersion
#endif
#ifndef MyCompression
  #define MyCompression "lzma2/max"
#endif

#ifndef MyAppVersion
  #error Build with /DMyAppVersion=<VERSION> through scripts\build_windows.ps1
#endif
#ifndef MyAppSourceDir
  #error Build with /DMyAppSourceDir=<PATH> through scripts\build_windows.ps1
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
VersionInfoVersion={#MyAppVersion}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} installer
DefaultDirName={localappdata}\Programs\FreshSense AI
DefaultGroupName=FreshSense AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; The build script overrides this with an explicit absolute /O path.
OutputDir=.
OutputBaseFilename={#MyOutputBaseFilename}
Compression={#MyCompression}
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
UsePreviousAppDir=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

#ifndef MySkipIcons
[Icons]
Name: "{group}\FreshSense AI"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\FreshSense AI"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
#endif

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch FreshSense AI"; Flags: nowait postinstall skipifsilent
