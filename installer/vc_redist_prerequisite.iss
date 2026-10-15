// Repack candidate: unchanged official installer, central Microsoft servicing.
// The frozen application payload and canonical CRT minimum stay unchanged.
const
  VcRuntimeKey = 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64';
  VcRedistSha256 = '843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c';
  VcRuntimeTermsUrl = 'https://visualstudio.microsoft.com/license-terms/vs2026-ga-visualcpp-v14-redist-runtime/';
  VcDistributionTermsUrl = 'https://visualstudio.microsoft.com/license-terms/vs2026-ga-community/';

var
  VcRedistRestartRequired: Boolean;
  VcTermsPage: TWizardPage;
  VcTermsCheckBox: TNewCheckBox;
  VcProgress: TOutputMarqueeProgressWizardPage;
  VcInstallConsent: Boolean;
  VcConsentRefused: Boolean;

function VcRedistCanLaunch: Boolean;
begin
  Result := not VcRedistRestartRequired;
end;

function VcVersionAtLeast(Major, Minor, Build, Revision: Cardinal): Boolean;
begin
  Result := (Major > 14) or
    ((Major = 14) and ((Minor > 51) or
      ((Minor = 51) and ((Build > 36247) or
        ((Build = 36247) and (Revision >= 0))))));
end;

function VcRuntimeVersionInView(RootKey: Integer): Boolean;
var
  Installed, Major, Minor, Build, Revision: Cardinal;
begin
  Result := RegQueryDWordValue(RootKey, VcRuntimeKey, 'Installed', Installed) and
    (Installed = 1) and
    RegQueryDWordValue(RootKey, VcRuntimeKey, 'Major', Major) and
    RegQueryDWordValue(RootKey, VcRuntimeKey, 'Minor', Minor) and
    RegQueryDWordValue(RootKey, VcRuntimeKey, 'Bld', Build) and
    RegQueryDWordValue(RootKey, VcRuntimeKey, 'Rbld', Revision);
  if Result then
    Result := VcVersionAtLeast(Major, Minor, Build, Revision);
end;

function VcCanonicalFileReady(const Name: String): Boolean;
var
  VersionMS, VersionLS: Cardinal;
begin
  Result := GetVersionNumbers(ExpandConstant('{sys}\') + Name, VersionMS, VersionLS);
  if Result then
    Result := VcVersionAtLeast(VersionMS shr 16, VersionMS and $FFFF,
      VersionLS shr 16, VersionLS and $FFFF);
end;

function VcRedistPrerequisiteReady: Boolean;
begin
  Result := IsWin64 and
    (VcRuntimeVersionInView(HKLM64) or VcRuntimeVersionInView(HKLM32)) and
    VcCanonicalFileReady('msvcp140.dll') and
    VcCanonicalFileReady('msvcp140_1.dll') and
    VcCanonicalFileReady('msvcp140_2.dll') and
    VcCanonicalFileReady('vcruntime140.dll') and
    VcCanonicalFileReady('vcruntime140_1.dll');
end;

function VcRedistPrerequisiteMessage: String;
begin
  Result := 'Το Microsoft Visual C++ x64 14.51.36247.0 ή νεότερο δεν επαληθεύτηκε. ' +
    'Το Mastixa Manager δεν εγκαταστάθηκε. Εγκαταστήστε το επίσημο πακέτο και δοκιμάστε ξανά.' + #13#10 +
    'https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist';
end;

function VcCommandLineHas(const Value: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Value) = 0 then
      Result := True;
end;

procedure UpdateVcRedistNextButton;
begin
  if WizardForm.CurPageID = VcTermsPage.ID then
    WizardForm.NextButton.Enabled := VcTermsCheckBox.Checked;
end;

procedure VcTermsChanged(Sender: TObject);
begin
  UpdateVcRedistNextButton;
end;

procedure VcLicenseLinkClick(Sender: TObject; const Link: String; LinkType: TSysLinkType);
var
  ErrorCode: Integer;
begin
  if (LinkType = sltURL) and ((Link = VcRuntimeTermsUrl) or (Link = VcDistributionTermsUrl)) then
    if not ShellExecAsOriginalUser('open', Link, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode) then
      MsgBox('Δεν ήταν δυνατό το άνοιγμα των όρων Microsoft στον προεπιλεγμένο φυλλομετρητή.', mbError, MB_OK);
end;

procedure InitializeVcRedistWizard;
var
  Explanation, TermsInfo: TNewStaticText;
  RuntimeLink, DistributionLink: TNewLinkLabel;
begin
  VcTermsPage := CreateCustomPage(wpLicense,
    'Mastixa Manager — Προαπαιτούμενο', 'Microsoft Visual C++ x64');
  Explanation := TNewStaticText.Create(VcTermsPage);
  Explanation.Parent := VcTermsPage.Surface;
  Explanation.Width := VcTermsPage.SurfaceWidth;
  Explanation.AutoSize := False;
  Explanation.WordWrap := True;
  Explanation.Caption := 'Για να λειτουργήσει το Mastixa Manager, απαιτείται ' +
    'Microsoft Visual C++ Redistributable x64 14.51.36247.0 ή νεότερο.' + #13#10 + #13#10 +
    'Το προαπαιτούμενο λείπει ή δεν είναι επαρκές. Μετά την αποδοχή των όρων ' +
    'θα ζητηθεί τελική επιβεβαίωση και, αν χρειάζεται, έγκριση διαχειριστή.';
  Explanation.AdjustHeight;
  TermsInfo := TNewStaticText.Create(VcTermsPage);
  TermsInfo.Parent := VcTermsPage.Surface;
  TermsInfo.Top := Explanation.Top + Explanation.Height + ScaleY(16);
  TermsInfo.Width := VcTermsPage.SurfaceWidth;
  TermsInfo.AutoSize := False;
  TermsInfo.WordWrap := True;
  TermsInfo.Caption := 'Οι όροι Microsoft αφορούν μόνο το πακέτο Microsoft. ' +
    'Τα δικαιώματα AGPL και αντικατάστασης καλυπτόμενων βιβλιοθηκών του Mastixa ' +
    'παραμένουν αμετάβλητα. Διαβάστε τους επίσημους όρους πριν συνεχίσετε:';
  TermsInfo.AdjustHeight;
  RuntimeLink := TNewLinkLabel.Create(VcTermsPage);
  RuntimeLink.Parent := VcTermsPage.Surface;
  RuntimeLink.Top := TermsInfo.Top + TermsInfo.Height + ScaleY(12);
  RuntimeLink.Width := VcTermsPage.SurfaceWidth;
  RuntimeLink.AutoSize := False;
  RuntimeLink.Caption := '<a href="' + VcRuntimeTermsUrl + '">Όροι χρήσης Microsoft Visual C++ Runtime</a>';
  RuntimeLink.OnLinkClick := @VcLicenseLinkClick;
  RuntimeLink.AdjustHeight;
  DistributionLink := TNewLinkLabel.Create(VcTermsPage);
  DistributionLink.Parent := VcTermsPage.Surface;
  DistributionLink.Top := RuntimeLink.Top + RuntimeLink.Height + ScaleY(8);
  DistributionLink.Width := VcTermsPage.SurfaceWidth;
  DistributionLink.AutoSize := False;
  DistributionLink.Caption := '<a href="' + VcDistributionTermsUrl + '">Όροι αναδιανομής — Visual Studio Community</a>';
  DistributionLink.OnLinkClick := @VcLicenseLinkClick;
  DistributionLink.AdjustHeight;
  VcTermsCheckBox := TNewCheckBox.Create(VcTermsPage);
  VcTermsCheckBox.Parent := VcTermsPage.Surface;
  VcTermsCheckBox.Top := DistributionLink.Top + DistributionLink.Height + ScaleY(18);
  VcTermsCheckBox.Width := VcTermsPage.SurfaceWidth;
  VcTermsCheckBox.Height := ScaleY(24);
  VcTermsCheckBox.Caption := 'Αποδέχομαι τους ισχύοντες όρους του πακέτου Microsoft.';
  VcTermsCheckBox.Checked := False;
  VcTermsCheckBox.OnClick := @VcTermsChanged;
  VcProgress := CreateOutputMarqueeProgressPage(
    'Mastixa Manager — Προαπαιτούμενο', 'Εγκατάσταση Microsoft Visual C++ x64');
end;

function VcRedistSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = VcTermsPage.ID) and (WizardSilent or VcRedistPrerequisiteReady);
end;

function VcRedistTermsAccepted(PageID: Integer): Boolean;
begin
  Result := True;
  if PageID <> VcTermsPage.ID then
    Exit;
  if VcRedistPrerequisiteReady then
    Exit;
  Result := VcTermsCheckBox.Checked or (WizardSilent and VcCommandLineHas('/ACCEPTVCRUNTIME'));
  if not Result then
    MsgBox('Για να συνεχίσετε, αποδεχθείτε τους όρους του πακέτου Microsoft.', mbError, MB_OK);
  if Result and (PageID = VcTermsPage.ID) and (not WizardSilent) and
    (not VcRedistPrerequisiteReady) and (not VcInstallConsent) then
  begin
    VcInstallConsent := MsgBox(
      'Το Mastixa Manager χρειάζεται Microsoft Visual C++ x64 14.51.36247.0 ή νεότερο.' + #13#10 +
      'Να εγκατασταθεί τώρα το επίσημο πακέτο; Θα ζητηθεί έγκριση διαχειριστή.' + #13#10 +
      'Αν επιλέξετε Όχι, η εγκατάσταση Mastixa Manager θα ακυρωθεί.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
    Result := VcInstallConsent;
    if not Result then
    begin
      VcConsentRefused := True;
      Log('VCREDIST: REFUSED; cancel before application installation.');
      WizardForm.Close;
    end;
  end;
end;

function EnsureVcRedist(var NeedsRestart: Boolean): String;
var
  Redist, Arguments: String;
  ExitCode: Integer;
  Started: Boolean;
begin
  Result := '';
  if VcRedistPrerequisiteReady then
  begin
    Log('VCREDIST: SKIP; adequate or newer x64 runtime and canonical files.');
    Exit;
  end;
  if (WizardSilent and not VcCommandLineHas('/ACCEPTVCRUNTIME')) or
    ((not WizardSilent) and not VcTermsCheckBox.Checked) then
  begin
    Result := 'Απαιτείται αποδοχή των όρων Microsoft. Η εγκατάσταση χωρίς διάλογο ' +
      'απαιτεί προηγούμενη αποδοχή και /ACCEPTVCRUNTIME.';
    Exit;
  end;
  if (WizardSilent and not VcCommandLineHas('/INSTALLVCRUNTIME')) or
    ((not WizardSilent) and not VcInstallConsent) then
  begin
    Result := 'Δεν δόθηκε συγκατάθεση για εγκατάσταση Microsoft Visual C++. ' +
      'Το Mastixa Manager δεν εγκαταστάθηκε. Χωρίς διάλογο απαιτείται /INSTALLVCRUNTIME.';
    Exit;
  end;
  if WizardSilent then
  begin
    if not VcCommandLineHas('/NORESTART') then
    begin
      Result := 'Η εγκατάσταση προαπαιτούμενου χωρίς διάλογο απαιτεί /NORESTART.';
      Exit;
    end;
    if not IsAdmin then
    begin
      Result := 'Εκτελέστε την εγκατάσταση χωρίς διάλογο ως διαχειριστής όταν λείπει το προαπαιτούμενο.';
      Exit;
    end;
  end;
  VcProgress.SetText('Εγκατάσταση Microsoft Visual C++ x64. Παρακαλώ περιμένετε…',
    'Η διαδικασία μπορεί να διαρκέσει αρκετά λεπτά. Δεν υπάρχει αξιόπιστο ποσοστό προόδου.');
  VcProgress.Show;
  VcProgress.Animate;
  try
  ExtractTemporaryFile('vc_redist.x64.exe');
  Redist := ExpandConstant('{tmp}\vc_redist.x64.exe');
  if CompareText(GetSHA256OfFile(Redist), VcRedistSha256) <> 0 then
  begin
    Result := 'Απέτυχε η επαλήθευση SHA-256 του πακέτου Microsoft. Η εγκατάσταση σταμάτησε.';
    Exit;
  end;
  Arguments := '/install /quiet /norestart /log "' +
    ExpandConstant('{tmp}\mastixa-vc-redist.log') + '"';
  if IsAdmin then
    Started := Exec(Redist, Arguments, '', SW_HIDE, ewWaitUntilTerminated, ExitCode)
  else
    Started := ShellExec('runas', Redist, Arguments, '', SW_HIDE,
      ewWaitUntilTerminated, ExitCode);
  Log(Format('VCREDIST: started=%d; exit=%d', [Ord(Started), ExitCode]));
  if not Started then
  begin
    Result := Format('Το πακέτο Microsoft δεν ξεκίνησε (σφάλμα Windows %d). ' +
      'Απαιτείται έγκριση διαχειριστή. Το Mastixa Manager δεν εγκαταστάθηκε.', [ExitCode]);
    Exit;
  end;
  if (ExitCode = 3010) or (ExitCode = 1641) then
  begin
    VcRedistRestartRequired := True;
    { Always defer application installation, even when files already look ready. }
    NeedsRestart := True;
    Result := 'Το Microsoft Visual C++ απαιτεί επανεκκίνηση. Επανεκκινήστε τα Windows ' +
      'και εκτελέστε ξανά την εγκατάσταση Mastixa Manager.';
    Exit;
  end
  else if (ExitCode <> 0) and (ExitCode <> 1638) and (ExitCode <> -2147023258) then
  begin
    Result := Format('Η εγκατάσταση Microsoft Visual C++ απέτυχε (κωδικός %d). ' +
      'Το Mastixa Manager δεν εγκαταστάθηκε.', [ExitCode]);
    Exit;
  end;
  { 1638 / HRESULT 0x80070666 is accepted only if a competing newer install is ready. }
  if not VcRedistPrerequisiteReady then
    Result := VcRedistPrerequisiteMessage;
  finally
    VcProgress.Hide;
  end;
end;
