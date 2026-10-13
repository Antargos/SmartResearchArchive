; Per-user installation: no administrator rights, no changes to PDF folders.
[Setup]
AppId={{8EA479A2-C80C-4E44-B3DC-6D412E7A704D}
AppName=Smart Research Archive
AppVersion=1.0.0
AppPublisher=Antargos
AppSupportURL=https://github.com/Antargos/SmartResearchArchive/issues
DefaultDirName={localappdata}\Programs\SmartResearchArchive
DefaultGroupName=Smart Research Archive
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\artifacts
OutputBaseFilename=SmartResearchArchive-1.0.0-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\SmartResearchArchive.exe

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; Flags: unchecked

[Files]
Source: "..\dist\SmartResearchArchive\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Smart Research Archive"; Filename: "{app}\SmartResearchArchive.exe"
Name: "{autodesktop}\Smart Research Archive"; Filename: "{app}\SmartResearchArchive.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SmartResearchArchive.exe"; Description: "Smart Research Archive starten"; Flags: nowait postinstall skipifsilent

; Credentials live separately in LocalAppData and PDFs in the selected folder.
; Neither is deleted by the uninstaller.
