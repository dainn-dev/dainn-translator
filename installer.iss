; ============================================================================
; Inno Setup Installer Script for Dainn Screen Translator
; ============================================================================
; BUILD INSTRUCTIONS:
; 1. First, build the application with PyInstaller:
;    pyinstaller DainnScreenTranslator.spec
; 2. This will create the output directory: dist\DainnScreenTranslator\
; 3. Then compile this installer script in Inno Setup
; ============================================================================

#define MyAppName "Dainn Screen Translator"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Dainn"
#define MyAppURL "https://github.com/dainn/trans"
#define MyAppExeName "DainnScreenTranslator.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{F8B0B0B0-B0B0-B0B0-B0B0-B0B0B0B0B0B0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
; Uncomment the following line to run in administrative install mode (install for all users.)
;PrivilegesRequired=admin
OutputDir=installer
OutputBaseFilename=DainnScreenTranslator_Setup_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Uncomment the following line if you want to sign the installer (requires signtool)
;SignTool=signtool
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName}
VersionInfoCopyright=Copyright (C) 2024 {#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; IMPORTANT: Make sure you've run 'pyinstaller DainnScreenTranslator.spec' first!
; This will create the dist\DainnScreenTranslator\ directory with all required files.
; Copy all files from PyInstaller output directory
Source: "dist\DainnScreenTranslator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Dirs]
Name: "{app}\config"; Flags: uninsalwaysuninstall
Name: "{app}\resources"; Flags: uninsalwaysuninstall

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel2.Caption := 'This will install Dainn Screen Translator on your computer.'#13#13'Dainn Screen Translator is a real-time screen translator that helps you translate text from your screen instantly using Google Cloud Vision and Translation APIs.';
end;

[UninstallDelete]
Type: dirifempty; Name: "{app}\config"
Type: dirifempty; Name: "{app}\resources"
Type: dirifempty; Name: "{app}"