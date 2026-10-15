"""Source contracts and synthetic link files only; no native installation or COM."""
import ast
import copy
import hashlib
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "installer/MastixaManager.iss"
HARNESS = ROOT / "tools/installer_validate.py"


def icon_entries(source):
    section = source.split("[Icons]", 1)[1].split("[", 1)[0]
    return [dict((key, value.strip('"')) for key, value in
                 re.findall(r'(\w+):\s*("[^"]*"|[^;]+)', line))
            for line in section.splitlines() if line.startswith("Name:")]


def helpers():
    parsed = ast.parse(HARNESS.read_text(encoding="utf-8"))
    names = {"digest", "shortcut_snapshot", "compare_shortcuts", "compare_preferences"}
    nodes = [node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {"hashlib": hashlib}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(HARNESS), "exec"), namespace)
    return namespace, parsed


class InstallerShortcutSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.iss = INSTALLER.read_text(encoding="utf-8")

    def test_noicons_can_set_wizard_state_even_with_hidden_group_page(self):
        # Inno 6.7.3 initializes NoIconsCheck from /NOICONS only with AllowNoIcons.
        self.assertRegex(self.iss, r"(?m)^AllowNoIcons=yes$")
        self.assertRegex(self.iss, r"(?m)^DisableProgramGroupPage=yes$")

    def test_start_menu_has_explicit_condition_and_keeps_normal_shortcut_contract(self):
        start_menu = next(entry for entry in icon_entries(self.iss)
                          if entry["Name"].startswith("{autoprograms}"))
        # False WizardNoIcons still permits the same shortcut with the same target.
        self.assertEqual({"Name": r"{autoprograms}\Mastixa Manager",
                          "Filename": r"{app}\{#MyAppExeName}",
                          "Check": "not WizardNoIcons"}, start_menu)

    def test_desktop_explicit_task_contract_is_unchanged_and_no_extra_icons_exist(self):
        entries = icon_entries(self.iss)
        self.assertEqual(2, len(entries))
        self.assertEqual({"Name": r"{autodesktop}\Mastixa Manager",
                          "Filename": r"{app}\{#MyAppExeName}", "Tasks": "desktopicon"}, entries[1])
        self.assertIn('Name: "desktopicon";', self.iss)
        task = self.iss.split("[Tasks]", 1)[1].split("[Files]", 1)[0]
        self.assertIn("Flags: unchecked", task)


class ShortcutSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.functions, self.parsed = helpers()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.link = self.out / "synthetic-start-menu.lnk"

    def snapshot(self):
        return self.functions["shortcut_snapshot"]([self.link])

    def test_existing_and_missing_links_are_observed_without_writing(self):
        self.assertEqual({str(self.link): None}, self.snapshot())
        self.link.write_bytes(b"synthetic prior link contents")
        before = self.link.stat()
        snapshot = self.snapshot()[str(self.link)]
        self.assertEqual(hashlib.sha256(self.link.read_bytes()).hexdigest(), snapshot["sha256"])
        self.assertEqual(before.st_size, snapshot["size"])
        self.assertEqual(before.st_mtime_ns, snapshot["mtime_ns"])
        self.assertEqual(b"synthetic prior link contents", self.link.read_bytes())
        self.assertEqual(before.st_mtime_ns, self.link.stat().st_mtime_ns)

    def test_creation_overwrite_deletion_and_timestamp_changes_record_exact_differences(self):
        compare = self.functions["compare_shortcuts"]
        path = str(self.link)
        missing = {path: None}
        original = {path: {"sha256": "original", "size": 10, "mtime_ns": 100}}
        for before, after in ((missing, original), (original, missing),
                              (original, {path: {"sha256": "changed", "size": 10, "mtime_ns": 100}}),
                              (original, {path: {"sha256": "original", "size": 10, "mtime_ns": 101}})):
            with self.subTest(before=before, after=after):
                retained = copy.deepcopy(before)
                self.assertEqual({"unchanged": False, "changed_paths": [path],
                                  "before": before, "after": after}, compare(before, after))
                self.assertEqual(retained, before)
        self.assertTrue(compare(original, copy.deepcopy(original))["unchanged"])

    def test_access_denied_fails_closed_instead_of_looking_like_missing_link(self):
        class UnreadablePath:
            def stat(self):
                raise PermissionError("synthetic permission failure")
        with self.assertRaises(PermissionError):
            self.functions["shortcut_snapshot"]([UnreadablePath()])

    def guard_namespace(self, before, mutation=None):
        """Exercise actual nested guards with synthetic files and a process stub."""
        report = {"stages": [], "shortcut_before": before}
        saved, launched = [], []
        def save():
            saved.append(copy.deepcopy(report))
        def process_stub(command, **kwargs):
            launched.append(command)
            if mutation:
                mutation()
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        namespace = dict(self.functions, before=None, winreg=object(), PREFERENCE_KEY="synthetic",
                         reg_snapshot=lambda *args: None, production=object(), tree=lambda *args: {},
                         production_before={}, shortcuts=[self.link], shortcut_before=before,
                         report=report, save=save, out=self.out, env={},
                         subprocess=SimpleNamespace(run=process_stub))
        main = next(node for node in self.parsed.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        nodes = [node for node in main.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"check_state", "run"}]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(HARNESS), "exec"), namespace)
        return namespace, saved, launched

    def test_noicons_creation_or_overwrite_halts_after_recording_without_restoration(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    self.link.write_bytes(b"synthetic prior shortcut")
                elif self.link.exists():
                    self.link.unlink()  # Synthetic test directory only.
                before = self.snapshot()
                namespace, saved, launched = self.guard_namespace(
                    before, mutation=lambda: self.link.write_bytes(b"synthetic changed shortcut"))
                with self.assertRaisesRegex(RuntimeError, "/NOICONS shortcut state changed"):
                    namespace["run"]("synthetic-install", ["process-stub", "/NOICONS"], 1)
                self.assertEqual(1, len(launched))
                comparison = saved[-1]["shortcut_checks"][-1]
                self.assertFalse(comparison["unchanged"])
                self.assertEqual(before, comparison["before"])
                self.assertEqual(self.snapshot(), comparison["after"])
                self.assertEqual(b"synthetic changed shortcut", self.link.read_bytes())
                with self.assertRaises(RuntimeError):
                    namespace["run"]("must-not-launch", ["process-stub"], 1)
                self.assertEqual(1, len(launched))  # No next process after the failure.

    def test_concurrent_shortcut_change_stops_before_any_process_launch(self):
        before = self.snapshot()
        namespace, saved, launched = self.guard_namespace(before)
        self.link.write_bytes(b"synthetic externally created shortcut")
        with self.assertRaises(RuntimeError):
            namespace["run"]("must-not-launch", ["process-stub", "/NOICONS"], 1)
        self.assertEqual([], launched)
        self.assertFalse(saved[-1]["shortcuts_unchanged"])

    def test_before_snapshot_is_persisted_before_native_cycle_and_noicons_is_mandatory(self):
        main = next(node for node in self.parsed.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        text = ast.unparse(main)
        self.assertIn("'shortcut_before': shortcut_before", text)
        self.assertLess(text.index("shortcut_before = shortcut_snapshot(shortcuts)"), text.index("out.mkdir("))
        cycle = next(node for node in main.body if isinstance(node, ast.Try))
        cycle_index = main.body.index(cycle)
        self.assertEqual("save()", ast.unparse(main.body[cycle_index - 1]))
        install = next(node for node in main.body if isinstance(node, ast.FunctionDef) and node.name == "install")
        self.assertIn("'/NOICONS'", ast.unparse(install))
        self.assertIn("'/TASKS='", ast.unparse(install))
        self.assertNotIn("uninstall(", ast.unparse(cycle.handlers[0]))
        guard = next(node for node in main.body if isinstance(node, ast.FunctionDef) and node.name == "check_state")
        # Guard only observes and records state; no shortcut writer or COM Save.
        self.assertNotRegex(ast.unparse(guard), r"write_|unlink|rename|replace|CreateShortcut|\.Save")


if __name__ == "__main__":
    unittest.main()
