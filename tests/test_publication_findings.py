"""Synthetic detector specimens; reports never include matched sensitive values."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('public_audit',Path(__file__).resolve().parents[1]/'tools/audit_public_source.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class PublicationFindingsTests(unittest.TestCase):
    def kinds(self,data):return {r['kind'] for r in audit.publication_findings(data,'fixture.txt')}

    def test_personal_windows_path(self):
        self.assertIn('personal-path',self.kinds(('C:/'+'Users/'+'synthetic-owner/notes').encode()))

    def test_personal_unix_path(self):
        self.assertIn('personal-path',self.kinds(('/'+'home/'+'synthetic-owner/build').encode()))

    def test_harmless_build_path_is_not_personal(self):
        self.assertEqual(set(),self.kinds(b'C:/SourceWork/build/output'))

    def test_public_provenance_is_preserved(self):
        self.assertEqual(set(),self.kinds(b'https://example.org/source/v1/archive.tar.xz'))

    def test_token_detected_without_echo(self):
        token=('gh'+'p_'+'A'*30).encode();result=audit.publication_findings(token,'fixture.txt')
        self.assertIn('credential-token',{r['kind'] for r in result})
        self.assertNotIn(token.decode(),str(result))

    def test_literal_password_assignment(self):
        specimen=('pass'+'word = '+repr('synthetic'+'-password')).encode()
        self.assertIn('credential-assignment',self.kinds(specimen))

    def test_literal_api_key_assignment(self):
        specimen=('api_'+'key = '+repr('synthetic'+'-api-value')).encode()
        self.assertIn('credential-assignment',self.kinds(specimen))

    def test_encrypted_private_key(self):
        specimen=('-----BEGIN '+'ENCRYPTED PRIVATE KEY'+'-----').encode()
        self.assertIn('encrypted-private-key',self.kinds(specimen))

    def test_unencrypted_private_key_preserves_original_check(self):
        specimen=('-----BEGIN '+'RSA PRIVATE KEY'+'-----').encode()
        self.assertIn('private-key',self.kinds(specimen))

    def test_utf16_secret_is_detected(self):
        specimen=('client_'+'secret = '+repr('synthetic'+'-value')).encode('utf-16')
        self.assertIn('credential-assignment',self.kinds(specimen))

    def test_connection_password_field_detected(self):
        specimen=('Server=local;Pass'+'word='+'synthetic-value;').encode()
        self.assertIn('connection-credential',self.kinds(specimen))

    def test_localized_wizard_label_is_not_password_field(self):
        self.assertEqual(set(),self.kinds('WizardPassword=Κωδικός πρόσβασης'.encode()))

    def test_fake_credentials_are_not_globally_waived(self):
        specimen=('pass'+'word = '+repr('example'+'-value')).encode()
        self.assertIn('credential-assignment',self.kinds(specimen))

    def test_existing_detector_findings_are_never_disabled(self):
        specimen=('C:/'+'Users/'+'synthetic-owner/file\n'+'gh'+'p_'+'A'*30).encode()
        old={(r['path'],r['line'],r['kind']) for r in audit.text_findings(specimen,'fixture.txt')}
        new={(r['path'],r['line'],r['kind']) for r in audit.publication_findings(specimen,'fixture.txt')}
        self.assertTrue(old<=new)
