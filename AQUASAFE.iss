[Setup]
AppName=AQUASAFE
AppVersion=1.0.1
DefaultDirName={autopf}\AQUASAFE
DefaultGroupName=AQUASAFE
OutputDir=installer_output
OutputBaseFilename=AQUASAFE_Setup_1.0.1
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupIconFile=assets\aquasafe.ico

[Files]
Source: "dist\AQUASAFE.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\aquasafe.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\AQUASAFE"; Filename: "{app}\AQUASAFE.exe"; IconFilename: "{app}\aquasafe.ico"
Name: "{autodesktop}\AQUASAFE"; Filename: "{app}\AQUASAFE.exe"; IconFilename: "{app}\aquasafe.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\AQUASAFE.exe"; Description: "Launch AQUASAFE"; Flags: nowait postinstall skipifsilent