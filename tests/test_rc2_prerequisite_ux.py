"""Retained bundled-mode reference contracts, plus active external-mode boundary.

These historical routines are not included by the current installer.
"""
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PrerequisiteUxTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / 'installer/vc_redist_prerequisite.iss').read_text(encoding='utf-8')
        self.ensure = self.source.split('function EnsureVcRedist', 1)[1]

    def test_skip_precedes_install_consent_extraction_and_child_execution(self):
        skip = self.ensure.index('if VcRedistPrerequisiteReady then')
        for action in ("'/INSTALLVCRUNTIME'", "ExtractTemporaryFile", "Exec(Redist"):
            self.assertLess(skip, self.ensure.index(action))
        self.assertLess(skip, self.ensure.index("'/ACCEPTVCRUNTIME'"))
        self.assertIn('and (WizardSilent or VcRedistPrerequisiteReady)', self.source)

    def test_interactive_refusal_closes_setup_without_default_yes(self):
        consent = self.source.split('function VcRedistTermsAccepted', 1)[1].split('function EnsureVcRedist', 1)[0]
        self.assertIn('MB_YESNO or MB_DEFBUTTON2', consent)
        self.assertIn('VcConsentRefused := True;', consent)
        self.assertIn('WizardForm.Close;', consent)
        setup = (ROOT / 'installer/MastixaManager.iss').read_text()
        self.assertNotIn('#include "vc_redist_prerequisite.iss"', setup)
        self.assertNotIn('VcConsentRefused', setup)

    def test_silent_install_requires_distinct_assent_before_extraction(self):
        extract = self.ensure.index('ExtractTemporaryFile')
        for guard in ("'/ACCEPTVCRUNTIME'", "'/INSTALLVCRUNTIME'", "'/NORESTART'", 'if not IsAdmin then'):
            self.assertLess(self.ensure.index(guard), extract)

    def test_progress_is_indeterminate_and_hidden_in_finally(self):
        self.assertIn('CreateOutputMarqueeProgressPage', self.source)
        self.assertIn('VcProgress.Animate;', self.ensure)
        self.assertNotIn('SetProgress(', self.source)
        self.assertLess(self.ensure.index('VcProgress.Show;'), self.ensure.index('ExtractTemporaryFile'))
        self.assertIn('finally\n    VcProgress.Hide;', self.ensure)

    def test_both_restart_codes_unconditionally_defer_application_install(self):
        restart = self.ensure.split('if (ExitCode = 3010) or (ExitCode = 1641) then', 1)[1].split('else if', 1)[0]
        self.assertIn('NeedsRestart := True;', restart)
        self.assertIn('VcRedistRestartRequired := True;', restart)
        self.assertIn('Exit;', restart)
        self.assertNotIn('if ', restart)

    def test_existing_fail_closed_version_race_hash_and_postconditions_retained(self):
        for marker in ("'Installed', Installed", '(Installed = 1)', "VcCanonicalFileReady('vcruntime140_1.dll')",
                       'GetSHA256OfFile(Redist)', 'if not Started then', 'ExitCode <> 1638',
                       'ExitCode <> -2147023258', 'if not VcRedistPrerequisiteReady then'):
            self.assertIn(marker, self.source)

    def test_greek_messages_and_brand_are_present(self):
        setup = (ROOT / 'installer/MastixaManager.iss').read_text()
        self.assertIn('compiler:Default.isl,Greek.isl', setup)
        self.assertIn('Mastixa Manager — Προαπαιτούμενο', self.source)
        self.assertNotIn("Result := 'Microsoft", self.source)

    def test_candidate_source_snapshot_retains_required_greek_language_input(self):
        snapshot = runpy.run_path(str(ROOT / 'packaging/source_snapshot.py'))
        members = dict(snapshot['source_files'](ROOT))
        self.assertEqual((ROOT / 'installer/Greek.isl').read_bytes(), members['installer/Greek.isl'])

    def test_one_prerequisite_page_with_clickable_allowed_license_links(self):
        self.assertEqual(1, self.source.count('CreateCustomPage('))
        self.assertNotIn('VcPrerequisitePage', self.source)
        self.assertIn('RuntimeLink.OnLinkClick := @VcLicenseLinkClick;', self.source)
        self.assertIn('DistributionLink.OnLinkClick := @VcLicenseLinkClick;', self.source)
        self.assertIn('vs2026-ga-visualcpp-v14-redist-runtime/', self.source)
        self.assertIn("ShellExecAsOriginalUser('open', Link", self.source)

    def test_next_enabled_only_by_checkbox_on_prerequisite_page(self):
        self.assertIn('WizardForm.NextButton.Enabled := VcTermsCheckBox.Checked;', self.source)
        self.assertIn('VcTermsCheckBox.Checked := False;', self.source)
        self.assertIn('VcTermsCheckBox.OnClick := @VcTermsChanged;', self.source)

    def test_initial_year_marker_is_written_only_after_install_with_no_existing_state(self):
        setup = (ROOT / 'installer/MastixaManager.iss').read_text()
        marker = setup.split('procedure CurStepChanged', 1)[1].split('function IsSilentUninstall', 1)[0]
        self.assertIn('if CurStep <> ssPostInstall then', marker)
        self.assertLess(marker.index('if DirExists(UserDataDir) then'), marker.index('SaveStringToFile('))
        self.assertIn('installation-year.json', marker)
