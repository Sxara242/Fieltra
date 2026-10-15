#define MyAppName "Mastixa Manager"
#define MyAppVersion "1.0.0-rc.2"
#define MyAppExeName "MastixaManager.exe"
#ifndef MyAppSourceDir
  #define MyAppSourceDir "..\dist\MastixaManager"
#endif
#ifndef MyLauncherPath
  #define MyLauncherPath "..\build\windows-launcher\MastixaManager.exe"
#endif
#ifndef MyPrerequisiteMode
  #define MyPrerequisiteMode "external-launch"
#endif
#if MyPrerequisiteMode != "external-launch"
  #error Only external-launch is approved. Bundled runtime mode requires a separate review.
#endif

[Setup]
AppId={{B9B946A2-8711-4B35-9BCB-B40210E67357}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Mastixa Manager
LicenseFile=..\LICENSE
DefaultDirName={%LOCALAPPDATA}\Programs\Mastixa Manager
DefaultGroupName=Mastixa Manager
DisableProgramGroupPage=yes
AllowNoIcons=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=MastixaManager-{#MyAppVersion}-Setup
SetupIconFile=..\packaging\mastixa_manager.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=1.0.0.2
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=1.0.0.2

[Languages]
Name: "greek"; MessagesFile: "compiler:Default.isl,Greek.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyLauncherPath}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}\engine"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Mastixa Manager"; Filename: "{app}\{#MyAppExeName}"; Check: not WizardNoIcons
Name: "{autodesktop}\Mastixa Manager"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; No installer-created preference namespace is required by the application.
; Ordinary uninstall/reinstall keeps existing preferences. Only full purge deletes them.

[UninstallDelete]
; The install directory is dedicated to Mastixa Manager. Remove any runtime/build residue
; that was created inside it but was not tracked as an installed file by Inno Setup.
; User databases, profiles and backups live separately under %LOCALAPPDATA%\MastixaManager
; and are preserved by default unless the user explicitly requests a full data purge.
Type: filesandordirs; Name: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Mastixa Manager}"; Flags: nowait postinstall skipifsilent

[Code]
// Runtime detection belongs to the independent launcher. No VC package/page/run hook.
// The previous bundled implementation is retained separately for engineering reference.

const
  MastixaUninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{B9B946A2-8711-4B35-9BCB-B40210E67357}_is1';

var
  DeleteUserDataOnUninstall: Boolean;
  ExistingInstallDetected: Boolean;
  InstalledVersion: String;
  MaintenanceMode: String;
  MaintenancePage: TInputOptionWizardPage;

function CmdLineParamExists(const Value: string): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Value) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

procedure InitializeWizard;
var
  CurrentVersion: String;
begin
  CurrentVersion := '{#MyAppVersion}';
  ExistingInstallDetected := RegKeyExists(HKCU, MastixaUninstallKey);
  InstalledVersion := '';
  MaintenanceMode := 'install';

  if not ExistingInstallDetected then
    Exit;

  if not RegQueryStringValue(
    HKCU,
    MastixaUninstallKey,
    'DisplayVersion',
    InstalledVersion) then
  begin
    InstalledVersion := 'unknown';
  end;

  if CompareText(InstalledVersion, CurrentVersion) = 0 then
  begin
    MaintenanceMode := 'repair';
    MaintenancePage := CreateInputOptionPage(
      wpWelcome,
      'Βρέθηκε υπάρχουσα εγκατάσταση',
      'Το Mastixa Manager ' + CurrentVersion + ' είναι ήδη εγκατεστημένο.',
      'Επιλέξτε επιδιόρθωση για επαναφορά αρχείων εφαρμογής και συντομεύσεων. ' +
      'Η τοπική βάση, τα προφίλ, τα έγγραφα, τα αρχεία καταγραφής και τα αντίγραφα ασφαλείας διατηρούνται.',
      True,
      False);
    MaintenancePage.Add('Επιδιόρθωση εγκατάστασης (συνιστάται)');
    MaintenancePage.SelectedValueIndex := 0;
  end
  else
  begin
    MaintenanceMode := 'update';
    MaintenancePage := CreateInputOptionPage(
      wpWelcome,
      'Βρέθηκε υπάρχουσα εγκατάσταση',
      'Εγκατεστημένη έκδοση: ' + InstalledVersion + '    Νέα έκδοση: ' + CurrentVersion,
      'Επιλέξτε ενημέρωση για αντικατάσταση αρχείων εφαρμογής με αυτή την έκδοση. ' +
      'Η τοπική βάση, τα προφίλ, τα έγγραφα, τα αρχεία καταγραφής και τα αντίγραφα ασφαλείας διατηρούνται.',
      True,
      False);
    MaintenancePage.Add('Ενημέρωση στην έκδοση ' + CurrentVersion + ' (συνιστάται)');
    MaintenancePage.SelectedValueIndex := 0;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  if ExistingInstallDetected then
    Log(
      'Existing Mastixa Manager installation detected. Mode=' + MaintenanceMode +
      '; installed=' + InstalledVersion + '; target={#MyAppVersion}');
  Result := ''; { Installation never depends on VC++ presence. }
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  UserDataDir, MetadataDir, Marker: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  UserDataDir := ExpandConstant('{localappdata}\MastixaManager');
  { Existing state may predate this installer. Never label it as a fresh install. }
  if DirExists(UserDataDir) then
    Exit;
  MetadataDir := UserDataDir + '\data';
  Marker := MetadataDir + '\installation-year.json';
  if ForceDirectories(MetadataDir) then
    if not SaveStringToFile(Marker,
      '{"schema":1,"year":' + GetDateTimeString('yyyy', '-', ':') + '}', False) then
      Log('Installation-year marker could not be saved. Application will retain a safe first-start fallback.');
end;

function IsSilentUninstall: Boolean;
begin
  Result := CmdLineParamExists('/SILENT') or CmdLineParamExists('/VERYSILENT');
end;

function InitializeUninstall: Boolean;
begin
  { Safe default: keep user data and preferences. /PURGEDATA explicitly purges both. }
  DeleteUserDataOnUninstall := CmdLineParamExists('/PURGEDATA');

  if (not DeleteUserDataOnUninstall) and (not IsSilentUninstall) then
  begin
    DeleteUserDataOnUninstall :=
      SuppressibleMsgBox(
        'Να διαγραφούν οριστικά όλα τα τοπικά δεδομένα, οι προτιμήσεις, τα προφίλ, τα έγγραφα, τα αρχεία καταγραφής και τα αντίγραφα ασφαλείας του Mastixa Manager;' + #13#10 + #13#10 +
        'Επιλέξτε Όχι για διατήρηση των δεδομένων σε επανεγκατάσταση ή αναβάθμιση.',
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2,
        IDNO) = IDYES;
  end;

  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataDir: String;
begin
  if (CurUninstallStep = usPostUninstall) and DeleteUserDataOnUninstall then
  begin
    if RegKeyExists(HKCU, 'Software\Mastixa\Mastixa Manager') then
    begin
      Log('Full uninstall requested. Removing Mastixa Manager preferences.');
      if not RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Mastixa\Mastixa Manager') then
        Log('Warning: Mastixa Manager preferences could not be removed.');
    end;
    UserDataDir := ExpandConstant('{localappdata}\MastixaManager');
    if DirExists(UserDataDir) then
    begin
      Log('Full uninstall requested. Removing user data: ' + UserDataDir);
      if not DelTree(UserDataDir, True, True, True) then
        Log('Warning: some Mastixa Manager user data could not be removed.');
    end;
  end;
end;
