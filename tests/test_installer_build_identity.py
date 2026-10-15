import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer_identity', ROOT / 'packaging/installer_identity.py')
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


class BuildIdentityTests(unittest.TestCase):
    def test_compiled_pascal_fixture_expectations_match_independent_reference(self):
        source = (ROOT / 'installer/maintenance_identity.iss').read_text()
        rows = re.findall(r"if MaintenanceModeFor\((True|False), '([^']*)', '([^']*)', '([^']*)', '([^']*)', '([^']*)', '([^']*)'\) <> '([^']*)'", source)
        self.assertEqual(8, len(rows))
        for existing, old, old_id, old_anc, new, new_id, new_anc, expected in rows:
            with self.subTest(expected=expected, old=old, new=new):
                self.assertEqual(expected, identity.classify(existing == 'True', old, old_id,
                    old_anc.strip('|').split('|'), new, new_id, new_anc.strip('|').split('|')))

    def test_numeric_and_prerelease_ordering(self):
        versions = ['0.9.9', '1.0.0-alpha.2', '1.0.0-alpha.10', '1.0.0-beta.1',
                    '1.0.0-rc.2', '1.0.0-rc.10', '1.0.0', '1.0.1', '1.10.0', '2.0.0']
        for old, new in zip(versions, versions[1:]):
            self.assertEqual('upgrade', identity.classify(True, old, '', [], new, 'B', []))
            self.assertEqual('downgrade', identity.classify(True, new, '', [], old, 'A', []))
        for unknown in ('unknown', '', '1.0', '1.0.0-', '1.0.0-rc.foo', '01.0.0', '1000000.0.0'):
            self.assertEqual('review', identity.classify(True, unknown, '', [], '1.0.0', 'B', []))

    def test_legacy_recognition_requires_actual_reviewed_hashes(self):
        for legacy in identity.legacy_builds():
            self.assertEqual(legacy['id'], identity.identify_legacy(legacy['version'], legacy['files']))
            damaged = dict(legacy['files'], **{'MastixaManager.exe': '0' * 64})
            self.assertEqual('', identity.identify_legacy(legacy['version'], damaged))
            self.assertEqual('', identity.identify_legacy('1.0.0', legacy['files']))
        installer = (ROOT / 'installer/MastixaManager.iss').read_text()
        for legacy in identity.legacy_builds():
            self.assertNotIn(legacy['id'], installer)
            for sha in legacy['files'].values():
                self.assertNotIn(sha, installer)
        self.assertNotIn('CurrentFilename', installer)

    def test_content_identity_is_deterministic_and_explicit_ancestry_orders_builds(self):
        a = identity.create_identity({'engine/app.exe': 'a' * 64}, '1.0.0-rc.2')
        self.assertEqual(a, identity.create_identity({'engine/app.exe': 'a' * 64}, '1.0.0-rc.2'))
        b = identity.create_identity({'engine/app.exe': 'b' * 64}, '1.0.0-rc.2', [a])
        for old, new, expected in ((a, b, 'upgrade'), (b, a, 'downgrade'), (b, b, 'repair')):
            self.assertEqual(expected, identity.classify(True, '1.0.0-rc.2', old['id'], old['inputs']['ancestors'],
                '1.0.0-rc.2', new['id'], new['inputs']['ancestors']))
        unrelated = identity.create_identity({'engine/app.exe': 'c' * 64}, '1.0.0-rc.2')
        self.assertEqual('review', identity.classify(True, '1.0.0-rc.2', b['id'], b['inputs']['ancestors'],
            '1.0.0-rc.2', unrelated['id'], unrelated['inputs']['ancestors']))
        tampered = dict(a, id='0' * 64)
        with self.assertRaises(ValueError):
            identity.create_identity({}, '1.0.0-rc.2', [tampered])

    def test_identity_persistence_uses_inno_metadata_only(self):
        source = (ROOT / 'installer/MastixaManager.iss').read_text()
        event = source.split('procedure RegisterPreviousData', 1)[1].split('function PrepareToInstall', 1)[0]
        self.assertIn("SetPreviousData(PreviousDataKey, 'BuildId'", event)
        self.assertNotIn('RegWrite', event)
        self.assertNotIn('[Registry]', source)
        self.assertIn('/ALLOWUNVERIFIEDBUILD', source)
