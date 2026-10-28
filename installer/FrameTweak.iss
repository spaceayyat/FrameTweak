; Inno Setup 6 script. Installs per-user by default (no admin needed); user may choose all-users at the prompt.
[Setup]
AppName=FrameTweak
AppVersion=0.3.0
AppPublisher=FrameTweak
DefaultDirName={autopf}\FrameTweak
DefaultGroupName=FrameTweak
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist-installer
OutputBaseFilename=FrameTweak-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName=FrameTweak

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\FrameTweak\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\FrameTweak"; Filename: "{app}\FrameTweak.exe"
Name: "{autodesktop}\FrameTweak"; Filename: "{app}\FrameTweak.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FrameTweak.exe"; Description: "Launch FrameTweak"; Flags: nowait postinstall skipifsilent
