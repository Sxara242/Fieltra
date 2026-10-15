"""Source contracts and synthetic snapshots; never run an installer or real registry API."""
import ast
import copy
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
KEY = r"Software\Fieltra\Fieltra"
HARNESS = ROOT / "tools/installer_validate.py"


def helper_functions():
    """Compile only pure/read-injected helpers, never import or execute the harness."""
    source = ast.parse(HARNESS.read_text(encoding="utf-8"))
    names = {"reg_snapshot", "compare_preferences", "check_installer_identity"}
    nodes = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
    blocked = next(node.value.value for node in source.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "BLOCKED_INSTALLER_SHA256" for t in node.targets))
    blocked_hashes = next(node.value for node in source.body if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "BLOCKED_INSTALLER_SHA256S"
                                  for t in node.targets))
    namespace = {"BLOCKED_INSTALLER_SHA256": blocked}
    namespace["BLOCKED_INSTALLER_SHA256S"] = tuple(
        blocked if isinstance(node, ast.Name) else node.value for node in blocked_hashes.elts)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(HARNESS), "exec"), namespace)
    return namespace


class FakeRegistry:
    """Only exposes read operations; a write/rename request would fail the test."""
    HKEY_CURRENT_USER = "synthetic-hkcu"
    KEY_READ = 0x20019

    def __init__(self, state):
        self.state = copy.deepcopy(state)
        self.opened = []
        self.error = None

    class Handle:
        def __init__(self, node):
            self.node = node
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def OpenKey(self, root, key, reserved, access):
        if (root, reserved, access) != (self.HKEY_CURRENT_USER, 0, self.KEY_READ):
            raise AssertionError("Snapshot requested non-read access")
        self.opened.append(key)
        if self.state is None:
            raise FileNotFoundError(key)
        node = self.state
        for child in key.removeprefix(KEY).strip("\\").split("\\"):
            if child:
                node = node["children"][child]
        return self.Handle(node)

    def EnumValue(self, handle, index):
        if self.error:
            raise self.error
        values = handle.node["values"]
        if index < len(values):
            return values[index]
        error = OSError("No more items")
        error.winerror = 259
        raise error

    def EnumKey(self, handle, index):
        keys = list(handle.node["children"])
        if index < len(keys):
            return keys[index]
        error = OSError("No more items")
        error.winerror = 259
        raise error


class InstallerPreferenceSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.iss = (ROOT / "installer/MastixaManager.iss").read_text(encoding="utf-8")
        cls.purge = cls.iss.split("procedure CurUninstallStepChanged", 1)[1]

    def test_normal_uninstall_has_no_preference_deletion_flags(self):
        self.assertNotIn("[Registry]", self.iss)
        self.assertNotIn("uninsdelete", self.iss)
        self.assertEqual(1, self.iss.count("RegDeleteKeyIncludingSubkeys("))

    def test_install_and_reinstall_do_not_overwrite_values_or_subkeys(self):
        self.assertNotIn("[Registry]", self.iss)
        self.assertNotRegex(self.iss, r"Reg(?:Write|Create)\w*\(")
        code = self.iss.split("procedure CurUninstallStepChanged", 1)[0]
        self.assertNotRegex(code, r"RegDelete\w+\(")

    def test_only_explicit_full_purge_deletes_preferences(self):
        # Match the entire procedure: no registry deletion before/after the opt-in block.
        expected = r"""procedure CurUninstallStepChanged\(CurUninstallStep: TUninstallStep\);
var
  UserDataDir: String;
begin
  if \(CurUninstallStep = usPostUninstall\) and DeleteUserDataOnUninstall then
  begin
    if RegKeyExists\(HKCU, 'Software\\Fieltra\\Fieltra'\) then
    begin
      Log\('Full uninstall requested\. Removing Fieltra preferences\.'\);
      if not RegDeleteKeyIncludingSubkeys\(HKCU, 'Software\\Fieltra\\Fieltra'\) then
        Log\('Warning: Fieltra preferences could not be removed\.'\);
    end;
    UserDataDir := ExpandConstant\('\{localappdata\}\\Fieltra'\);
    if DirExists\(UserDataDir\) then
    begin
      Log\('Full uninstall requested\. Removing user data: ' \+ UserDataDir\);
      if not DelTree\(UserDataDir, True, True, True\) then
        Log\('Warning: some Fieltra user data could not be removed\.'\);
    end;
  end;
end;
"""
        self.assertRegex(self.iss, expected + r"\s*\Z")
        self.assertIn("DeleteUserDataOnUninstall := CmdLineParamExists('/PURGEDATA')", self.iss)
        self.assertIn("(not DeleteUserDataOnUninstall) and (not IsSilentUninstall)", self.iss)
        self.assertIn("MB_YESNO or MB_DEFBUTTON2", self.iss)
        self.assertIn("IDNO) = IDYES", self.iss)
        self.assertIn("τοπικά δεδομένα, οι προτιμήσεις, τα προφίλ", self.iss)

    def test_harness_contains_only_read_registry_calls_and_no_rename_workaround(self):
        text = HARNESS.read_text(encoding="utf-8")
        parsed = ast.parse(text)
        for forbidden in ("RegRenameKey", "NtRenameKey", "ctypes", "KEY_ALL_ACCESS", "PRESERVED"):
            self.assertNotIn(forbidden, text)
        calls = {node.func.attr for node in ast.walk(parsed) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                 and node.func.value.id in {"registry", "winreg"}}
        self.assertEqual({"OpenKey", "EnumValue", "EnumKey", "QueryValueEx"}, calls)
        self.assertNotIn(".rename(", text)
        self.assertNotIn("/PURGEDATA", text)  # Real-user validation never purges.

    def test_harness_top_level_cannot_launch_validation_on_import(self):
        parsed = ast.parse(HARNESS.read_text(encoding="utf-8"))
        for node in parsed.body:
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                self.assertTrue(set(targets) <= {"ROOT", "PREFERENCE_KEY", "UNINSTALL_KEY",
                                                "BLOCKED_INSTALLER_SHA256", "BLOCKED_INSTALLER_SHA256S"})
            else:
                self.assertIsInstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Expr, ast.If))
                if isinstance(node, ast.Expr):
                    self.assertIsInstance(node.value, ast.Constant)
                if isinstance(node, ast.If):
                    self.assertEqual("__name__ == '__main__'", ast.unparse(node.test))
        main = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        text = ast.unparse(main)
        self.assertLess(text.index("if not args.execute:"), text.index("subprocess.run("))
        self.assertLess(text.index("check_installer_identity("), text.index("import winreg"))
        for isolation in ("/NOICONS", "/DIR=", "MASTIXA_DATA_HOME", "TEMP=", "TMP="):
            self.assertIn(isolation, text)
        # Failure handling can only observe/save, never restore or launch cleanup.
        outer_try = next(n for n in main.body if isinstance(n, ast.Try))
        failure = ast.unparse(outer_try.handlers[0])
        self.assertNotIn("uninstall(", failure)
        self.assertIn("status='BLOCKED'", failure)
        self.assertIn("check_state('failure')", failure)


class PreferenceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.helpers = helper_functions()
        self.state = {"values": [("theme", "dark", 1), ("binary", b"\x00\xff", 3)],
                      "children": {"window": {"values": [("width", 1200, 4)], "children": {}}}}

    def snapshot(self, state):
        registry = FakeRegistry(state)
        result = self.helpers["reg_snapshot"](KEY, registry)
        self.assertEqual(state, registry.state)  # Snapshot cannot mutate synthetic data.
        return result

    def test_snapshot_preserves_values_types_binary_and_nested_keys_read_only(self):
        result = self.snapshot(self.state)
        self.assertEqual([["binary", "b'\\x00\\xff'", 3], ["theme", "'dark'", 1]], result["values"])
        self.assertEqual([["width", "1200", 4]], result["children"]["window"]["values"])

    def test_identical_snapshots_pass_even_if_enumeration_order_changes(self):
        reordered = copy.deepcopy(self.state)
        reordered["values"].reverse()
        comparison = self.helpers["compare_preferences"](self.snapshot(self.state), self.snapshot(reordered))
        self.assertTrue(comparison["unchanged"])

    def test_changes_record_both_snapshots_without_restoration(self):
        for kind in ("value", "subkey", "deleted", "type"):
            with self.subTest(kind=kind):
                changed = copy.deepcopy(self.state)
                if kind == "value":
                    changed["values"][0] = ("theme", "light", 1)
                elif kind == "subkey":
                    changed["children"].clear()
                elif kind == "type":
                    changed["values"][0] = ("theme", "dark", 2)
                else:
                    changed = None
                before, after = self.snapshot(self.state), self.snapshot(changed)
                difference = self.helpers["compare_preferences"](before, after)
                self.assertEqual({"unchanged": False, "before": before, "after": after}, difference)

    def test_access_denied_is_not_reported_as_an_empty_snapshot(self):
        registry = FakeRegistry(self.state)
        registry.error = PermissionError("synthetic access denied")
        registry.error.winerror = 5
        with self.assertRaises(PermissionError):
            self.helpers["reg_snapshot"](KEY, registry)

    def test_existing_empty_key_is_distinct_from_missing_key(self):
        self.assertEqual({"values": [], "children": {}}, self.snapshot({"values": [], "children": {}}))
        self.assertIsNone(self.snapshot(None))

    def test_defective_candidate_is_rejected_even_if_operator_supplies_its_hash(self):
        for bad in self.helpers["BLOCKED_INSTALLER_SHA256S"]:
            with self.subTest(hash=bad), self.assertRaisesRegex(RuntimeError, "rebuild required"):
                self.helpers["check_installer_identity"](bad, bad)

    def test_changed_candidate_is_rejected_and_matching_new_identity_is_accepted(self):
        with self.assertRaises(RuntimeError):
            self.helpers["check_installer_identity"]("a" * 64, "b" * 64)
        with self.assertRaises(ValueError):
            self.helpers["check_installer_identity"]("a" * 64, "invalid")
        self.helpers["check_installer_identity"]("a" * 64, "a" * 64)


if __name__ == "__main__":
    unittest.main()
