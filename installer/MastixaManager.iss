#define MyAppName "Fieltra"
#define MyAppVersion "1.0.0"
#define MyAppExeName "Fieltra.exe"
#ifndef MyBuildIdentityFile
  #error Build identity required. Use packaging/build_external_vc_candidate.ps1.
#endif
#include MyBuildIdentityFile
#ifndef MyAppSourceDir
  #define MyAppSourceDir "..\dist\Fieltra"
#endif
#ifndef MyLauncherPath
  #define MyLauncherPath "..\build\windows-launcher\Fieltra.exe"
#endif
#ifndef MyPrerequisiteMode
  #define MyPrerequisiteMode "external-launch"
#endif
#if MyPrerequisiteMode != "external-launch"
  #error Only external-launch is approved. Bundled runtime mode requires a separate review.
#endif

[Setup]
AppId={{8A6CE872-CC79-4605-9084-893E304E38AD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Fieltra
LicenseFile=..\LICENSE
DefaultDirName={%LOCALAPPDATA}\Programs\Fieltra
DefaultGroupName=Fieltra
DisableProgramGroupPage=yes
AllowNoIcons=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=Fieltra-{#MyAppVersion}-Setup
SetupIconFile=..\packaging\mastixa_manager.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=1.0.0.0
VersionInfoTextVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=1.0.0.0
VersionInfoProductTextVersion={#MyAppVersion}

[Languages]
Name: "greek"; MessagesFile: "compiler:Default.isl,Greek.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyLauncherPath}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}\engine"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Fieltra"; Filename: "{app}\{#MyAppExeName}"; Check: not WizardNoIcons
Name: "{autodesktop}\Fieltra"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; No installer-created preference namespace is required by the application.
; Ordinary uninstall/reinstall keeps existing preferences. Only full purge deletes them.

[UninstallDelete]
; The install directory is dedicated to Fieltra. Remove any runtime/build residue
; that was created inside it but was not tracked as an installed file by Inno Setup.
; User databases, profiles and backups live separately under %LOCALAPPDATA%\Fieltra
; and are preserved by default unless the user explicitly requests a full data purge.
Type: filesandordirs; Name: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Fieltra}"; Flags: nowait postinstall skipifsilent

[Code]
#include "maintenance_identity.iss"
// Runtime detection belongs to the independent launcher. No VC package/page/run hook.
// The previous bundled implementation is retained separately for engineering reference.

const
  MastixaUninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8A6CE872-CC79-4605-9084-893E304E38AD}_is1';

var
  DeleteUserDataOnUninstall: Boolean;
  ExistingInstallDetected: Boolean;
  InstalledVersion: String;
  InstalledBuildId: String;
  InstalledBuildAncestors: String;
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
  CurrentVersion, Description, Choice: String;
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

  InstalledBuildId := GetPreviousData('BuildId', '');
  InstalledBuildAncestors := GetPreviousData('BuildAncestors', '');
  if GetPreviousData('BuildVersion', '') <> InstalledVersion then begin
    InstalledBuildId := '';
    InstalledBuildAncestors := '';
  end;
  MaintenanceMode := MaintenanceModeFor(True, InstalledVersion, InstalledBuildId,
    InstalledBuildAncestors, CurrentVersion, '{#MyBuildId}', '{#MyBuildAncestors}');
  if MaintenanceMode = 'repair' then begin
    Description := 'Το ίδιο build είναι ήδη εγκατεστημένο. Επαναφορά αρχείων εφαρμογής και συντομεύσεων.';
    Choice := 'Επιδιόρθωση εγκατάστασης (συνιστάται)';
  end else if MaintenanceMode = 'upgrade' then begin
    Description := 'Εγκατεστημένη έκδοση: ' + InstalledVersion + '    Έκδοση αναβάθμισης: ' + CurrentVersion;
    Choice := 'Αναβάθμιση εγκατάστασης (συνιστάται)';
  end else if MaintenanceMode = 'downgrade' then begin
    Description := 'Προσοχή: η εγκατεστημένη έκδοση ή το build είναι νεότερο. Η υποβάθμιση μπορεί να μην υποστηρίζει τα υπάρχοντα δεδομένα.';
    Choice := 'Υποβάθμιση — απαιτείται επιβεβαίωση';
  end else begin
    Description := 'Δεν επιβεβαιώθηκε η σειρά των builds. Η αντικατάσταση μπορεί να μην υποστηρίζει τα υπάρχοντα δεδομένα.';
    Choice := 'Αντικατάσταση μη επαληθευμένου build — απαιτείται επιβεβαίωση';
  end;
  MaintenancePage := CreateInputOptionPage(wpWelcome, 'Βρέθηκε υπάρχουσα εγκατάσταση',
    Description, 'Η τοπική βάση, τα προφίλ, τα έγγραφα, τα αρχεία καταγραφής και τα αντίγραφα ασφαλείας διατηρούνται.', True, False);
  MaintenancePage.Add(Choice);
  MaintenancePage.SelectedValueIndex := 0;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if not ExistingInstallDetected then Exit;
  if (CurPageID = MaintenancePage.ID) and
     ((MaintenanceMode = 'downgrade') or (MaintenanceMode = 'review')) then
    Result := SuppressibleMsgBox('Προσοχή: υποβάθμιση ή μη επαληθευμένη αντικατάσταση. ' +
      'Κρατήστε αντίγραφο ασφαλείας πριν συνεχίσετε. Θέλετε να συνεχίσετε;',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  { Inno's own uninstall metadata; no application preference/profile key. }
  SetPreviousData(PreviousDataKey, 'BuildVersion', '{#MyAppVersion}');
  SetPreviousData(PreviousDataKey, 'BuildId', '{#MyBuildId}');
  SetPreviousData(PreviousDataKey, 'BuildAncestors', '{#MyBuildAncestors}');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  if ExistingInstallDetected then
    Log(
      'Existing Fieltra installation detected. Mode=' + MaintenanceMode +
      '; installed=' + InstalledVersion + '; installed-build=' + InstalledBuildId +
      '; target={#MyAppVersion}; target-build={#MyBuildId}');
  Result := ''; { Installation never depends on VC++ presence. }
  if WizardSilent then begin
    if (MaintenanceMode = 'downgrade') and not CmdLineParamExists('/ALLOWDOWNGRADE') then
      Result := 'Η υποβάθμιση απαιτεί /ALLOWDOWNGRADE και προηγούμενο αντίγραφο ασφαλείας.';
    if (MaintenanceMode = 'review') and not CmdLineParamExists('/ALLOWUNVERIFIEDBUILD') then
      Result := 'Η μη επαληθευμένη αντικατάσταση απαιτεί /ALLOWUNVERIFIEDBUILD.';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  UserDataDir, MetadataDir, Marker: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  UserDataDir := ExpandConstant('{localappdata}\Fieltra');
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
        'Να διαγραφούν οριστικά όλα τα τοπικά δεδομένα, οι προτιμήσεις, τα προφίλ, τα έγγραφα, τα αρχεία καταγραφής και τα αντίγραφα ασφαλείας του Fieltra;' + #13#10 + #13#10 +
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
    if RegKeyExists(HKCU, 'Software\Fieltra\Fieltra') then
    begin
      Log('Full uninstall requested. Removing Fieltra preferences.');
      if not RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Fieltra\Fieltra') then
        Log('Warning: Fieltra preferences could not be removed.');
    end;
    UserDataDir := ExpandConstant('{localappdata}\Fieltra');
    if DirExists(UserDataDir) then
    begin
      Log('Full uninstall requested. Removing user data: ' + UserDataDir);
      if not DelTree(UserDataDir, True, True, True) then
        Log('Warning: some Fieltra user data could not be removed.');
    end;
  end;
end;
