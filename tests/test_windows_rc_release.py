"""RC release safety, channel behavior and actual packaging-filter regressions."""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import update_manager
from app.version import APP_LICENSE, APP_VERSION, RELEASE_CHANNEL, is_newer_version
from tests.test_alpha2_updates import _manifest, _Response


ROOT = Path(__file__).resolve().parents[1]
gate = runpy.run_path(str(ROOT / "packaging/validate_windows_release.py"))
exclude = runpy.run_path(str(ROOT / "packaging/qt_exclusions.py"))["without_virtualkeyboard"]


class WindowsRcReleaseTests(unittest.TestCase):
    def test_geonames_resource_has_hash_locked_source_attribution_and_shipping_license(self):
        name='app/assets/geonames_gr.json'
        ledger=json.loads((ROOT/'docs/asset-provenance.json').read_text(encoding='utf-8'))
        items=[item for item in ledger if item['path']==name]
        self.assertEqual(1,len(items))
        item=items[0]
        source=ROOT/name
        data=json.loads(source.read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),item['sha256'])
        self.assertEqual('CC-BY-4.0',item['license'])
        self.assertTrue(item['ships_windows'])
        for field in ('source_sha256','acquired_at','source_last_modified'):
            self.assertEqual(data[field],item[field])
        self.assertEqual(data['source'],item['origin'])
        notices=(ROOT/'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
        for text in (name,item['origin'],'GeoNames','CC BY 4.0','filters the original records'):
            self.assertIn(text,notices)
        manifest=json.loads((ROOT/'licenses/manifest.json').read_text(encoding='utf-8'))
        license_item=next(entry for entry in manifest['texts']+manifest.get('attributions',[]) if entry['path']==item['license_file'])
        self.assertTrue(license_item['shipping'])
        self.assertEqual('REQUIRED AND SHIPS',license_item['classification'])
        self.assertEqual(license_item['sha256'],hashlib.sha256((ROOT/item['license_file']).read_bytes()).hexdigest())

    def test_resource_gate_still_rejects_unlisted_or_changed_geonames_data(self):
        ledger_path=ROOT/'docs/asset-provenance.json'
        original_read=Path.read_text
        ledger=json.loads(original_read(ledger_path,encoding='utf-8'))
        name='app/assets/geonames_gr.json'
        for missing in (True,False):
            altered=[dict(item) for item in ledger if not (missing and item['path']==name)]
            if not missing:
                next(item for item in altered if item['path']==name)['sha256']='0'*64
            def read(path,*args,**kwargs):
                return json.dumps(altered) if path==ledger_path else original_read(path,*args,**kwargs)
            with self.subTest(missing=missing), patch.object(Path,'read_text',new=read):
                errors=gate['configuration_errors']()
            self.assertIn('Resource provenance inventory is incomplete' if missing else
                          'Resource missing/changed: '+name,errors)

    def test_development_metadata_cannot_build_with_retained_stable_configuration(self):
        self.assertEqual(("1.0.1-alpha.1", "alpha", "AGPL-3.0-only"),
                         (APP_VERSION, RELEASE_CHANNEL, APP_LICENSE))
        self.assertCountEqual(['Release metadata mismatch: version',
                               'Release metadata mismatch: channel'],
                              gate["configuration_errors"]())
        with self.assertRaisesRegex(RuntimeError, "BLOCKED BEFORE RC BUILD"):
            gate["require_ready"]()
        self.assertIn('LicenseFile=..\\LICENSE', (ROOT / 'installer/MastixaManager.iss').read_text())

    def test_preflight_refuses_incomplete_native_legal_and_source_delivery(self):
        config = json.loads((ROOT / 'packaging/windows-rc.json').read_text())
        config['distribution_legal_gates']['B3']['legal_status'] = 'BLOCKED'
        errors = gate["legal_readiness_errors"](config)
        self.assertTrue(any("B3-LEGAL" in message for message in errors))
        self.assertFalse(any("CI logs" in message or "bit-identical" in message for message in errors))
        self.assertCountEqual(['Release metadata mismatch: version',
                               'Release metadata mismatch: channel'],
                              gate["preflight_errors"]())
        with patch.dict(gate["require_ready"].__globals__, preflight_errors=lambda root: errors):
            with self.assertRaisesRegex(RuntimeError, "BLOCKED BEFORE RC BUILD"):
                gate["require_ready"]()

    def test_virtualkeyboard_filter_removes_indirect_plugin_dll_qml_and_preserves_input(self):
        entries = [
            (r'PySide6\Qt6VirtualKeyboard.dll', r'C:\wheel\Qt6VirtualKeyboard.dll', 'BINARY'),
            ('PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll', 'wheel/plugin.dll', 'BINARY'),
            ('qml/QtQuick/VirtualKeyboard/qmldir', 'wheel/qmldir', 'DATA'),
            ('unremarkable.dll', r'C:\wheel\Qt6VirtualKeyboard.dll', 'BINARY'),
            ('PySide6/plugins/platforms/qwindows.dll', 'wheel/qwindows.dll', 'BINARY'),
            ('PySide6/Qt6Gui.dll', 'wheel/Qt6Gui.dll', 'BINARY'),
        ]
        self.assertEqual(entries[-2:], exclude(entries))

    def test_virtualkeyboard_has_no_windows_runtime_source_dependency(self):
        import ast
        for path in [ROOT / 'main.py', *(ROOT / 'app').rglob('*.py')]:
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [alias.name for alias in node.names]
                    names.append(getattr(node, 'module', '') or '')
                    self.assertFalse(any('virtualkeyboard' in name.casefold() for name in names), path)
            self.assertNotIn('QT_IM_MODULE', path.read_text(encoding='utf-8-sig'))

    def test_default_staging_check_is_offline_no_update(self):
        opener = Mock(side_effect=AssertionError('Staging reached network'))
        info = update_manager.fetch_update_info(opener=opener)
        self.assertEqual(RELEASE_CHANNEL, info.channel)
        self.assertFalse(info.is_newer)
        self.assertIsNone(info.windows)
        opener.assert_not_called()

    def test_stable_rc_and_legacy_ordering(self):
        for candidate, current, expected in [('1.0.0-rc.3', '1.0.0-rc.2', True),
                ('1.0.0-rc.10','1.0.0-rc.9',True),('1.0.0','1.0.0-rc.2',True),
                ('1.0.0-rc.2','1.0.0',False),('1.0.0','1.0.0',False),
                ('0.40.0-alpha.2','1.0.0',False),
                ('1.0.1-alpha.1','1.0.0',True),
                ('1.0.1-alpha.2','1.0.1-alpha.1',True),
                ('1.0.1-alpha.1','1.0.1-alpha.1',False)]:
            with self.subTest(candidate=candidate,current=current):
                self.assertEqual(expected,is_newer_version(candidate,current))
        stable = update_manager.parse_manifest(_manifest(version='1.0.0', channel='stable'), expected_channel='stable')
        self.assertEqual('stable',stable.channel)

    def test_default_staging_also_rejects_non_project_artifact_before_download(self):
        with tempfile.TemporaryDirectory() as temp:
            feed=Path(temp)/'rc.json'
            feed.write_bytes(_manifest(version=APP_VERSION, channel=RELEASE_CHANNEL, windows={'filename':'setup.exe',
                             'url':'https://example.invalid/setup.exe','sha256':'a'*64}))
            opener=Mock(side_effect=AssertionError('Invalid staging artifact reached network'))
            with patch.object(update_manager,'STAGING_FEED',feed), self.assertRaises(update_manager.UpdateError):
                update_manager.fetch_update_info(opener=opener)
            opener.assert_not_called()

    def test_rejects_wrong_channel_and_suffix_without_downloading(self):
        for version, channel, expected in [('1.0.0-rc.2','stable','stable'),
                ('1.0.0','rc','rc'),('1.0.0','stable','rc'),('1.0.0-rc.2','rc','stable')]:
            with self.subTest(version=version,channel=channel), self.assertRaises(update_manager.UpdateError):
                update_manager.parse_manifest(_manifest(version=version,channel=channel), expected_channel=expected)

    def test_operational_feed_accepts_project_github_release_artifact(self):
        for repository in ('Fieltra', 'Mastixa-Manager-Source'):
            with self.subTest(repository=repository):
                payload=_manifest(version='1.0.1-alpha.2', channel='alpha',
                    windows={'filename':'Fieltra-1.0.1-alpha.2-Setup.exe',
                    'url':f'https://github.com/Sxara242/{repository}/releases/download/v1.0.1-alpha.2/Fieltra-1.0.1-alpha.2-Setup.exe',
                    'sha256':'a'*64})
                info=update_manager.fetch_update_info('https://example.invalid/staging.json', expected_channel='alpha',
                    opener=Mock(return_value=_Response(payload)))
                self.assertTrue(info.is_newer)

    def test_operational_feed_rejects_unapproved_artifact_origin(self):
        for url in ('https://example.invalid/setup.exe',
                    'https://github.com/other/project/releases/download/v1/setup.exe',
                    'https://user@github.com/Sxara242/Fieltra/releases/download/v1/setup.exe',
                    'https://github.com/Sxara242/Fieltra-evil/releases/download/v1/setup.exe',
                    'https://github.com.evil.invalid/Sxara242/Fieltra/releases/download/v1/setup.exe',
                    'https://github.com:444/Sxara242/Fieltra/releases/download/v1/setup.exe'):
            with self.subTest(url=url), self.assertRaisesRegex(update_manager.UpdateError, 'project GitHub Releases'):
                update_manager.fetch_update_info('https://example.invalid/staging.json',expected_channel='alpha',
                    opener=Mock(return_value=_Response(_manifest(windows={
                        'filename':'setup.exe','url':url,'sha256':'a'*64}))))

    def test_actual_mismatch_after_success_never_overwrites_verified_bytes(self):
        good=b'verified staging installer'
        info=update_manager.parse_manifest(_manifest(windows={'filename':'setup.exe',
             'url':'https://example.invalid/setup.exe','sha256':hashlib.sha256(good).hexdigest()}))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            target=update_manager.download_windows_update(info,destination_dir=root,opener=Mock(return_value=_Response(good)))
            with self.assertRaisesRegex(update_manager.UpdateError,'SHA-256'):
                update_manager.download_windows_update(info,destination_dir=root,opener=Mock(return_value=_Response(b'tampered')))
            self.assertEqual(good,target.read_bytes())
            self.assertFalse((root/'setup.exe.part').exists())

    def test_download_timeout_partial_cleanup_then_real_retry_verifies_sha(self):
        good=b'retry installer bytes'
        info=update_manager.parse_manifest(_manifest(windows={'filename':'setup.exe',
             'url':'https://example.invalid/setup.exe','sha256':hashlib.sha256(good).hexdigest()}))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaisesRegex(update_manager.UpdateError,'timeout'):
                update_manager.download_windows_update(info,destination_dir=root,opener=Mock(side_effect=TimeoutError('timeout')))
            self.assertEqual([],list(root.iterdir()))
            path=update_manager.download_windows_update(info,destination_dir=root,opener=Mock(return_value=_Response(good)))
            self.assertEqual(good,path.read_bytes())

    def test_bundle_verifier_detects_missing_notice_and_virtualkeyboard(self):
        # This is a legal/privacy fixture, not the separately qualified EPSG bundle.
        actual_run_path = runpy.run_path
        def fixture_run_path(path, *args, **kwargs):
            if Path(path).name == 'epsg_provenance.py':
                return {'bundle_errors': lambda bundle, root: []}
            return actual_run_path(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as temp, patch.object(runpy, 'run_path', side_effect=fixture_run_path):
            bundle=Path(temp)
            internal=bundle/'_internal'
            legal_manifest=json.loads((ROOT/'licenses/manifest.json').read_text())
            names={x['path'] for x in legal_manifest['texts']+legal_manifest.get('attributions',[]) if x.get('shipping',True)}
            names.update({'THIRD_PARTY_NOTICES.md','licenses/manifest.json','DISTRIBUTION_SOURCE.md','SOURCE_DELIVERY_PLAN.md','source-artifacts.json',
                          'updates/staging/rc.json','updates/staging/stable.json'})
            for name in names:
                source=ROOT/('docs/'+name if name in {'DISTRIBUTION_SOURCE.md','SOURCE_DELIVERY_PLAN.md','source-artifacts.json'} else name)
                target=internal/name
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,target)
            self.assertEqual([],gate['bundle_errors'](bundle))
            (internal/'THIRD_PARTY_NOTICES.md').unlink()
            (internal/'Qt6VirtualKeyboard.dll').write_bytes(b'fixture')
            (internal/'owner.sqlite3').write_bytes(b'fixture')
            errors=gate['bundle_errors'](bundle)
            self.assertTrue(any('THIRD_PARTY_NOTICES' in x for x in errors))
            self.assertTrue(any('VirtualKeyboard' in x for x in errors))
            self.assertTrue(any('owner.sqlite3' in x for x in errors))
