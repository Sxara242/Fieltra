"""External VC launch/packaging boundaries; no real app/installer/registry access."""
import importlib.util
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('external_vc_layout', ROOT / 'packaging/external_vc_layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


class ExternalVcLauncherTests(unittest.TestCase):
    def test_installer_never_blocks_or_handles_runtime(self):
        setup = (ROOT / 'installer/MastixaManager.iss').read_text(encoding='utf-8')
        for obsolete in ('MyVcRedistPath', '#include "vc_redist_prerequisite.iss"',
                         'EnsureVcRedist', 'VcRedistCanLaunch', 'InitializeVcRedistWizard',
                         'VcTermsCheckBox', 'ExtractTemporaryFile', 'vc_redist.x64.exe'):
            self.assertNotIn(obsolete, setup)
        prepare = setup.split('function PrepareToInstall', 1)[1].split('procedure CurStepChanged', 1)[0]
        self.assertIn("Result := '';", prepare)
        self.assertNotIn('RegQuery', prepare)
        self.assertIn('#error Only external-launch is approved.', setup)

    def test_all_installer_entry_points_use_same_native_launcher(self):
        setup = (ROOT / 'installer/MastixaManager.iss').read_text(encoding='utf-8')
        self.assertIn('Source: "{#MyLauncherPath}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"', setup)
        self.assertIn('Source: "{#MyAppSourceDir}\\*"; DestDir: "{app}\\engine"', setup)
        for line in setup.splitlines():
            if line.startswith('Name: "{autoprograms}') or line.startswith('Name: "{autodesktop}') or line.startswith('Filename: '):
                self.assertIn('Filename: "{app}\\{#MyAppExeName}"', line)
        self.assertIn('Check: not WizardNoIcons', setup)
        self.assertIn('Flags: nowait postinstall skipifsilent', setup)

    def test_minimum_architecture_and_official_link_match_existing_policy(self):
        config = json.loads((ROOT / 'packaging/windows-prerequisite.json').read_text())
        existing = json.loads((ROOT / 'packaging/windows-crt-policy.json').read_text())
        self.assertEqual('external-launch', config['mode'])
        self.assertEqual('x64', config['architecture'])
        self.assertEqual(existing['minimum_version'], config['minimum_version'])
        self.assertEqual('14.51.36247.0', config['minimum_version'])
        self.assertEqual('https://aka.ms/vc14/vc_redist.x64.exe', config['download_url'])
        self.assertEqual(5, len(config['canonical_files']))

    def test_native_source_uses_read_only_x64_views_and_canonical_files(self):
        source = (ROOT / 'packaging/windows_launcher/launcher.c').read_text(encoding='utf-8')
        self.assertIn('Runtimes\\\\x64', source)
        self.assertIn('KEY_WOW64_64KEY', source)
        self.assertIn('KEY_WOW64_32KEY', source)
        self.assertIn('GetSystemDirectoryW', source)
        self.assertIn('REG_DWORD', source)
        for prohibited in ('RegSetValue', 'RegDeleteKey', 'WinHttp', 'URLDownload', 'LoadLibrary', 'runas'):
            self.assertNotIn(prohibited, source)
        self.assertIn('MastixaStartChild(&child, engine_path, command, engine_directory)', source)

    def test_greek_dialog_is_actionable_and_cancel_does_not_install(self):
        rc = (ROOT / 'packaging/windows_launcher/launcher.rc').read_text(encoding='utf-8')
        source = (ROOT / 'packaging/windows_launcher/launcher.c').read_text(encoding='utf-8')
        for text in ('Λήψη από Microsoft', 'Έλεγχος &ξανά', '&Ακύρωση', 'https://aka.ms/vc14/vc_redist.x64.exe'):
            self.assertIn(text, rc)
        self.assertIn('last_result = ProbeRuntime();', source)
        self.assertIn('EndDialog(window, IDCANCEL)', source)
        self.assertIn('ξεχωριστά', source)
        self.assertIn('ShellExecuteW(window, L"open", MASTIXA_DOWNLOAD_URL', source)

    def test_native_corresponding_source_is_retained(self):
        snapshot = runpy.run_path(str(ROOT / 'packaging/source_snapshot.py'))
        members = dict(snapshot['source_files'](ROOT))
        for name in ('launcher.c', 'guard.c', 'runtime_policy.h', 'arguments.h', 'job_child.h', 'launcher.rc', 'launcher.manifest'):
            path = 'packaging/windows_launcher/' + name
            self.assertEqual((ROOT / path).read_bytes(), members[path])
        self.assertIn('tests/native/test_windows_launcher.c', members)

    def test_synthetic_native_test_cannot_run_real_payload_or_registry(self):
        source = (ROOT / 'tests/native/test_windows_launcher.c').read_text(encoding='utf-8')
        for operation in ('RegOpenKey', 'CreateProcess', 'ShellExecute', 'DialogBox', 'LoadLibrary'):
            self.assertNotIn(operation, source)
        self.assertIn('CommandLineToArgvW', source)
        self.assertIn('VC_ACCESS_ERROR', source)
        self.assertIn('VC_WRONG_ARCH', source)

    def test_smoke_uses_launcher_with_engine_resources_and_owned_child_cleanup(self):
        source = (ROOT / 'packaging/smoke_test_packaged.ps1').read_text()
        self.assertIn('$resourceBundle = Join-Path $bundle "engine"', source)
        self.assertIn('$startInfo.FileName = $exe', source)
        self.assertIn('$process.Kill()', source)
        self.assertNotIn('Stop-Process -Name', source)
        self.assertNotIn('taskkill', source)
        child = (ROOT / 'packaging/windows_launcher/job_child.h').read_text()
        self.assertIn('CREATE_SUSPENDED', child)
        self.assertIn('JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE', child)
        self.assertIn('MastixaAllowChildDescendants', child)

    def test_existing_output_and_manifest_mismatch_never_modify_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); payload = root / 'payload'; payload.mkdir()
            app = payload / 'Fieltra.exe'; app.write_bytes(b'original')
            output = root / 'existing'; output.mkdir()
            with self.assertRaisesRegex(ValueError, 'Fresh output'):
                layout.create_layout(payload, root / 'launcher', output)
            with self.assertRaisesRegex(ValueError, 'differs from the retained'):
                layout.create_layout(payload, root / 'launcher', root / 'fresh', {'Fieltra.exe': '0'*64})
            self.assertEqual(b'original', app.read_bytes())
            self.assertFalse((root / 'fresh').exists())

    def test_runtime_dlls_and_installer_are_rejected_before_copy(self):
        for name in ('MSVCP140.dll', 'vcruntime140-hashed.dll', 'vc_redist.x64.exe'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                payload = Path(folder); (payload / name).write_bytes(b'fixture')
                with self.assertRaisesRegex(ValueError, 'runtime payload forbidden'):
                    layout.safe_files(payload)

    def test_layout_keeps_every_payload_byte_and_copies_only_one_launcher(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); payload = root / 'payload'; payload.mkdir()
            (payload / 'Fieltra.exe').write_bytes(b'unchanged frozen app')
            (payload / '_internal').mkdir(); (payload / '_internal/library.bin').write_bytes(b'library')
            launcher = root / 'native.exe'; launcher.write_bytes(b'native fixture')
            expected = layout.safe_files(payload)
            with patch.object(layout, 'verify_bundle'), patch.object(layout, 'audit_launcher', return_value={'sha256':layout.digest(launcher)}):
                result = layout.create_layout(payload, launcher, root / 'output', expected)
            self.assertEqual(expected, layout.safe_files(payload))
            self.assertEqual(expected, layout.safe_files(root / 'output/engine'))
            self.assertEqual(3, len(result['layout_members_sha256']))
            self.assertEqual(b'native fixture', (root / 'output/Fieltra.exe').read_bytes())


if __name__ == '__main__':
    unittest.main()
