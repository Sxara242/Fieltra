"""Repack boundaries: no native execution or owner registry access."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('split_verifier', ROOT/'packaging/verify_split_source.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class RepackagingTests(unittest.TestCase):
    def test_external_asset_is_required_before_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            record = {'external_assets': [{'materialized_path': 'dependencies/qt.tar.xz', 'filename': 'qt.tar.xz', 'size': 3, 'sha256': 'a'*64}],
                      'files': [{'path': 'dependencies/qt.tar.xz', 'size': 3, 'sha256': 'a'*64}]}
            (root/'RECIPIENT_MANIFEST.json').write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'Required separate'):
                verifier.verify(root)

    def test_corrupt_external_asset_fails_before_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); assets = root/'assets'; assets.mkdir()
            (assets/'qt.tar.xz').write_bytes(b'bad')
            record = {'external_assets': [{'materialized_path': 'dependencies/qt.tar.xz', 'filename': 'qt.tar.xz', 'size': 3, 'sha256': 'a'*64}],
                      'files': [{'path': 'dependencies/qt.tar.xz', 'size': 3, 'sha256': 'a'*64}]}
            (root/'RECIPIENT_MANIFEST.json').write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'Missing/changed'):
                verifier.verify(root, assets)

    def test_escape_and_duplicate_paths_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('../bad', '/absolute', 'C:/absolute', 'dir\\bad'):
                with self.assertRaises(ValueError): verifier.safe(Path(folder), name)

    def test_restart_and_failure_guards_are_present(self):
        text = (ROOT/'installer/vc_redist_prerequisite.iss').read_text()
        setup = (ROOT/'installer/MastixaManager.iss').read_text()
        self.assertNotIn('Check: VcRedistCanLaunch', setup)
        self.assertNotIn('#include "vc_redist_prerequisite.iss"', setup)
        self.assertIn('Result := not VcRedistRestartRequired;', text)
        self.assertIn("if not IsAdmin then", text)
        self.assertIn("'/NORESTART'", text)
        self.assertIn('if not Started then', text)
        self.assertIn('if not VcRedistPrerequisiteReady then', text)
        self.assertIn('ExitCode = 3010', text)
        self.assertIn('ExitCode = 1641', text)
        self.assertIn('ExitCode <> -2147023258', text)
        self.assertLess(text.index('if VcRedistPrerequisiteReady then'), text.index("ExtractTemporaryFile('vc_redist.x64.exe')"))
        terms = text[text.index('function VcRedistTermsAccepted'):text.index('function EnsureVcRedist')]
        # Adequate runtime skips all prompts; missing runtime still requires assent.
        self.assertLess(terms.index('if VcRedistPrerequisiteReady then'), terms.index('VcTermsCheckBox.Checked'))
        self.assertIn("VcTermsCheckBox.Checked or (WizardSilent and VcCommandLineHas('/ACCEPTVCRUNTIME'))", terms)


if __name__ == '__main__': unittest.main()
