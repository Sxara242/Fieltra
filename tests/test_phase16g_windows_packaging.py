from __future__ import annotations

from pathlib import Path
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import textwrap
import unittest

from app.runtime_paths import resolve_base_dir


ROOT = Path(__file__).resolve().parents[1]
REPORT_UPLOAD = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
TIMEOUT_MODULES = {
    "tests.test_activity_expense_sync": 240,
    "tests.test_batch5_ui": 120,
    "tests.test_batch7_exports": 120,
    "tests.test_stabilization": 360,
    "tests.test_transaction_integrity": 120,
    "tests.test_ui_revamp_phase1": 120,
    "tests.test_windows_owner_fix_batch1": 120,
}


class Phase16GWindowsPackagingTests(unittest.TestCase):
    def _read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_hosted_packaging_checks_do_not_generate_or_upload_installers(self) -> None:
        workflow = self._read(".github/workflows/windows-release-gate.yml")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("runs-on: windows-latest", workflow)
        self.assertIn("packaging/validate_windows_release.py", workflow)
        self.assertIn("tests.test_phase16g_windows_packaging", workflow)
        self.assertNotIn("self-hosted", workflow)
        self.assertNotIn("actions/upload-artifact", workflow)
        self.assertNotIn("build_release.ps1", workflow)
        self.assertNotIn("ci_windows_release.ps1", workflow)

    def test_smoke_isolates_child_environment_without_reusing_host_profile(self) -> None:
        smoke = self._read("packaging/smoke_test_packaged.ps1")
        for variable in ("MASTIXA_DATA_HOME", "LOCALAPPDATA", "APPDATA", "USERPROFILE",
                         "HOME", "HOMEDRIVE", "HOMEPATH", "TEMP", "TMP", "QT_QPA_PLATFORM"):
            self.assertIn(f'$startInfo.EnvironmentVariables["{variable}"] =', smoke)
        self.assertNotRegex(smoke, r"(?i)\$env:\w+\s*=")
        self.assertIn("$env:RUNNER_TEMP", smoke)
        self.assertIn("[guid]::NewGuid()", smoke)
        self.assertIn('$startInfo.WorkingDirectory = $isolationRoot', smoke)
        self.assertIn('$startInfo.UseShellExecute = $false', smoke)
        self.assertIn('"offscreen"', smoke)
        self.assertIn('"_internal\\data"', smoke)
        self.assertIn("Refusing a bundle", smoke)

    def test_smoke_requires_readiness_clean_exit_and_isolated_initialization(self) -> None:
        smoke = self._read("packaging/smoke_test_packaged.ps1")
        startup = self._read("app/main_window.py")
        self.assertIn('$startInfo.FileName = $exe', smoke)
        self.assertIn('$startInfo.Arguments = "--smoke-test"', smoke)
        self.assertIn('if ($exitCode -ne 0)', smoke)
        self.assertIn('Packaged smoke test started', smoke)
        self.assertIn('ERROR|CRITICAL', smoke)
        self.assertIn('data\\profiles.json', smoke)
        self.assertIn('data\\mastixa_manager.db', smoke)
        self.assertIn('if ($status -ne "PASS") { throw', smoke)
        self.assertLess(startup.index('controller.start()'),
                        startup.index('logger.info("Packaged smoke test started")'))
        self.assertIn('QTimer.singleShot(1200, app.quit)', startup)

    def test_smoke_bounds_waits_and_cleans_only_created_process(self) -> None:
        smoke = self._read("packaging/smoke_test_packaged.ps1")
        self.assertIn('[ValidateRange(5, 300)]', smoke)
        self.assertIn('$process.WaitForExit($TimeoutSeconds * 1000)', smoke)
        self.assertIn('$process.WaitForExit(5000)', smoke)
        self.assertIn('finally {', smoke)
        self.assertIn('$process.Kill()', smoke)
        self.assertIn('$process.StartInfo = $startInfo', smoke)
        self.assertIn('$started = $process.Start()', smoke)
        self.assertNotRegex(smoke, r'(?i)Stop-Process|taskkill|GetProcessesByName|WaitForExit\(\)')
        self.assertIn('ReadToEndAsync()', smoke)
        self.assertIn('result.json', smoke)

    def test_smoke_rejects_missing_or_changed_runtime_resources(self) -> None:
        smoke = self._read("packaging/smoke_test_packaged.ps1")
        self.assertIn('@("assets", "locales")', smoke)
        self.assertIn('Missing packaged resource:', smoke)
        self.assertIn('Packaged resource differs', smoke)
        self.assertIn('Get-FileHash', smoke)
        self.assertLess(smoke.index('Missing packaged resource:'), smoke.index('$process.Start()'))

    @unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell required")
    def test_smoke_parses_in_windows_powershell_and_rejects_missing_executable(self) -> None:
        script = ROOT / "packaging/smoke_test_packaged.ps1"
        parse = subprocess.run([
            "powershell.exe", "-NoProfile", "-Command",
            "$tokens=$null; $errors=$null; "
            "[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{str(script).replace(chr(39), chr(39) * 2)}',[ref]$tokens,[ref]$errors) | Out-Null; "
            "if ($errors.Count) { $errors | Out-String | Write-Output; exit 1 }",
        ], capture_output=True, text=True, timeout=20)
        self.assertEqual(0, parse.returncode, parse.stdout + parse.stderr)
        rejected = subprocess.run([
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
            "-ExecutablePath", str(ROOT / "nonexistent-smoke-bundle" / "Fieltra.exe"),
        ], capture_output=True, text=True, timeout=20)
        self.assertNotEqual(0, rejected.returncode)

    @unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell required")
    def test_smoke_runner_fails_closed_and_cleans_timeout_process(self) -> None:
        # A tiny executable tests the runner's failure paths; the real bundle
        # smoke remains a mandatory, separate release-workflow step.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # Python may inherit PowerShell 7's module path from a developer
            # shell. Let Windows PowerShell locate its own built-in modules.
            fixture_env = {key: value for key, value in os.environ.items()
                           if key.casefold() != "psmodulepath"}
            exe = root / "Fieltra.exe"
            source = root / "Fixture.cs"
            source.write_text('''
using System;
using System.IO;
using System.Diagnostics;
using System.Threading;
public class Fixture {
    public static int Main() {
        string mode = Environment.GetEnvironmentVariable("MASTIXA_RUNNER_FIXTURE");
        File.WriteAllText("fixture.pid", Process.GetCurrentProcess().Id.ToString());
        if (mode == "timeout") { Thread.Sleep(30000); return 0; }
        if (mode == "exit") return 17;
        if (mode == "no-marker") return 0;
        string data = Path.Combine(Environment.GetEnvironmentVariable("MASTIXA_DATA_HOME"), "data");
        Directory.CreateDirectory(Path.Combine(data, "logs"));
        File.WriteAllText(Path.Combine(data, "profiles.json"), "{}");
        File.WriteAllText(Path.Combine(data, "mastixa_manager.db"), "fixture");
        File.WriteAllText(Path.Combine(data, "logs", "mastixa_manager.log"),
            "| INFO | mastixa.main_window | Packaged smoke test started\\n" +
            (mode == "error" ? "| CRITICAL | mastixa | Unhandled exception\\n" : ""));
        return 0;
    }
}
''', encoding="utf-8")
            compiled = subprocess.run([
                "powershell.exe", "-NoProfile", "-Command",
                "Add-Type -Path $env:FIXTURE_SOURCE -OutputAssembly $env:FIXTURE_EXE "
                "-OutputType ConsoleApplication",
            ], env={**fixture_env, "FIXTURE_SOURCE": str(source), "FIXTURE_EXE": str(exe)},
                capture_output=True, text=True, timeout=30)
            self.assertEqual(0, compiled.returncode, compiled.stdout + compiled.stderr)
            for resource in ("assets", "locales"):
                shutil.copytree(ROOT / "app" / resource, root / "_internal" / "app" / resource)
            for mode, expected in (("exit", "FAIL"), ("no-marker", "FAIL"),
                                   ("error", "FAIL"), ("timeout", "FAIL"), ("success", "PASS")):
                with self.subTest(mode=mode):
                    run_root = root / mode
                    run_root.mkdir()
                    result = subprocess.run([
                        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "packaging/smoke_test_packaged.ps1"),
                        "-ExecutablePath", str(exe), "-TimeoutSeconds", "5",
                    ], env={**fixture_env, "RUNNER_TEMP": str(run_root),
                            "MASTIXA_RUNNER_FIXTURE": mode},
                        capture_output=True, text=True, timeout=20)
                    self.assertEqual(expected == "PASS", result.returncode == 0,
                                     result.stdout + result.stderr)
                    reports = list(run_root.glob("MastixaManager-smoke-*/result.json"))
                    self.assertEqual(1, len(reports), result.stdout + result.stderr)
                    report = json.loads(reports[0].read_text(encoding="utf-8-sig"))
                    self.assertEqual(expected, report["status"])
                    self.assertTrue(Path(report["isolatedData"]).is_relative_to(run_root))
                    if mode == "exit":
                        self.assertEqual(17, report["exitCode"])
                    if mode == "timeout":
                        self.assertIn("timed out", report["failure"])
                        pid = int((reports[0].parent / "fixture.pid").read_text())
                        check = subprocess.run([
                            "powershell.exe", "-NoProfile", "-Command",
                            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 1 }}",
                        ], capture_output=True, timeout=10)
                        self.assertEqual(0, check.returncode, "Timed-out child survived cleanup")

    def test_retained_release_packaging_versions_are_consistent(self) -> None:
        readme = self._read("README.md")
        iss = self._read("installer/MastixaManager.iss")
        version_info = self._read("packaging/version_info.txt")
        config = json.loads(self._read("packaging/windows-rc.json"))

        iss_match = re.search(r'^#define MyAppVersion "([^"]+)"', iss, re.MULTILINE)
        file_match = re.search(r"StringStruct\('FileVersion', '([^']+)'\)", version_info)
        product_match = re.search(r"StringStruct\('ProductVersion', '([^']+)'\)", version_info)

        for match in (
            iss_match,
            file_match,
            product_match,
        ):
            self.assertIsNotNone(match)

        versions = {
            config['version'],
            iss_match.group(1),
            file_match.group(1),
            product_match.group(1),
        }
        self.assertEqual({'1.0.0'}, versions, f"Retained release versions drifted: {sorted(versions)}")
        self.assertIn('/releases/tag/v1.0.0', readme)

    def test_installer_upgrade_contract_preserves_external_user_data(self) -> None:
        iss = self._read("installer/MastixaManager.iss")

        self.assertIn("AppId={{8A6CE872-CC79-4605-9084-893E304E38AD}", iss)
        self.assertIn("PrivilegesRequired=lowest", iss)
        self.assertIn("DefaultDirName={%LOCALAPPDATA}\\Programs\\Fieltra", iss)
        self.assertNotIn("MastixaManager\\data", iss)
        self.assertNotIn("MastixaManager\\backups", iss)

        data_dir = resolve_base_dir(
            frozen=True,
            environ={"LOCALAPPDATA": "C:/SyntheticProfiles/test/AppData/Local"},
        )
        install_dir = Path("C:/SyntheticProfiles/test/AppData/Local/Programs/Fieltra").resolve()
        self.assertEqual(
            Path("C:/SyntheticProfiles/test/AppData/Local/Fieltra").resolve(),
            data_dir,
        )
        self.assertNotEqual(install_dir, data_dir)
        self.assertNotIn(install_dir, data_dir.parents)

    def test_uninstaller_preserves_preferences_and_removes_install_residue(self) -> None:
        iss = self._read("installer/MastixaManager.iss")

        self.assertNotIn("[Registry]", iss)
        self.assertNotIn("uninsdeletekey", iss)
        self.assertIn("RegDeleteKeyIncludingSubkeys(HKCU, 'Software\\Fieltra\\Fieltra')", iss)
        self.assertNotIn("Microsoft\\Windows\\CurrentVersion\\UFH\\SHC", iss)

        self.assertIn("[UninstallDelete]", iss)
        self.assertIn('Type: filesandordirs; Name: "{app}"', iss)
        self.assertNotIn(
            'Type: filesandordirs; Name: "{%LOCALAPPDATA}\\Fieltra"',
            iss,
        )

    def test_bundle_contract_includes_runtime_assets_and_excludes_private_data(self) -> None:
        spec = self._read("packaging/MastixaManager.spec")
        build = self._read("packaging/build_release.ps1")

        self.assertIn('"app/assets"', spec)
        self.assertIn('"app/locales"', spec)
        self.assertNotIn('"data/mastixa_manager.db"', spec)
        self.assertNotIn('"backups"', spec)

        self.assertIn('"_internal\\data"', build)
        self.assertIn('Filter "*.db"', build)
        self.assertIn("Private application data unexpectedly entered the build", build)
        self.assertIn("Unexpected SQLite database files entered the release bundle", build)

    def test_database_privacy_gate_allows_only_pyproj_dependency_database(self) -> None:
        build = self._read("packaging/build_release.ps1")
        workflow = self._read(".github/workflows/windows-release-gate.yml")

        self.assertIn('$databaseFile.Name -ieq "proj.db"', build)
        self.assertIn('$relativePath -match "(^|/)pyproj(/|$)"', build)
        self.assertIn("Allowed dependency database", build)
        self.assertIn("$unexpectedDatabaseFiles", build)
        self.assertNotIn("SQLite database files unexpectedly entered the release bundle", build)
        self.assertIn("packaging/validate_windows_release.py", workflow)
        gate = self._read("packaging/validate_windows_release.py")
        self.assertIn('path.name.casefold() == "proj.db" and "pyproj" in lower.split("/")', gate)

    def test_release_builder_is_windows_powershell_compatible(self) -> None:
        build = self._read("packaging/build_release.ps1")

        self.assertIn("function Get-BundleRelativePath", build)
        self.assertIn("[System.StringComparison]::OrdinalIgnoreCase", build)
        self.assertNotIn("[System.IO.Path]::GetRelativePath", build)

    def test_hosted_checks_do_not_install_inno_or_use_a_private_runner(self) -> None:
        build = self._read("packaging/build_release.ps1")
        workflow = self._read(".github/workflows/windows-release-gate.yml")
        self.assertIn('Programs\\Inno Setup 6\\ISCC.exe', build)
        self.assertIn("runs-on: windows-latest", workflow)
        self.assertNotIn("self-hosted", workflow)
        self.assertNotIn("winget install", workflow)

    def test_release_output_is_isolated_and_stops_after_one_installer_attempt(self) -> None:
        build = self._read("packaging/build_release.ps1")
        ci_build = self._read("packaging/ci_windows_release.ps1")
        workflow = self._read(".github/workflows/windows-release-gate.yml")

        self.assertIn('[string]$InstallerOutputDir = ""', build)
        self.assertIn("[int]$InstallerBuildAttempts = 1", build)
        self.assertIn('if ($InstallerBuildAttempts -ne 1) { throw', build)
        self.assertIn('& $compiler "/O$installerOutput"', build)
        self.assertEqual(1, build.count('& $compiler '))
        self.assertIn('if ($LASTEXITCODE -ne 0) { throw', build)
        self.assertIn('No automatic retry.', build)
        self.assertNotRegex(build, r'for\s*\(\s*\$attempt\b')
        self.assertIn('$outputDir = Join-Path $env:RUNNER_TEMP', ci_build)
        self.assertIn('$env:GITHUB_RUN_ID', ci_build)
        self.assertIn('$env:GITHUB_RUN_ATTEMPT', ci_build)
        self.assertIn("-InstallerOutputDir $outputDir", ci_build)
        self.assertIn("-InstallerBuildAttempts 1", ci_build)
        self.assertNotIn("-InstallerBuildAttempts 3", ci_build)
        self.assertNotIn("ci_windows_release.ps1", workflow)
        self.assertNotIn('dist\\installer\\Fieltra-', workflow)

    def test_release_gate_uses_tracked_non_invasive_lock_diagnostics(self) -> None:
        ci_build = self._read("packaging/ci_windows_release.ps1")
        workflow = self._read(".github/workflows/windows-release-gate.yml")

        self.assertIn("download.sysinternals.com/files/Handle.zip", ci_build)
        self.assertIn("Get-AuthenticodeSignature", ci_build)
        self.assertIn('-notmatch "Microsoft"', ci_build)
        self.assertIn("Start-Job", ci_build)
        self.assertIn("Observed installer file locks", ci_build)
        self.assertNotIn("ci_windows_release.ps1", workflow)
        self.assertNotIn("shell: powershell", workflow)
        self.assertNotIn("Stop-Process", ci_build)
        self.assertNotIn("Add-MpPreference", ci_build)
        self.assertNotIn("Set-MpPreference", ci_build)

    def test_ci_storage_is_manual_only_and_short_lived(self) -> None:
        for name in ("verify.yml", "windows-release-gate.yml"):
            self.assertNotIn("actions/upload-artifact", self._read(".github/workflows/" + name))
        self._assert_android_runtime_report_policy(self._read(".github/workflows/android-runtime.yml"))
        workflow = self._read(".github/workflows/android-update-gate.yml")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("  push:", workflow)
        self.assertIn("if: ${{ inputs.upload_apk }}", workflow)
        self.assertIn("retention-days: 1", workflow)

    def _workflow_fields(self, text):
        """Read only the reviewed block-mapping shape, not arbitrary YAML.

        No YAML dependency is declared. Reject duplicate/ambiguous root keys and
        unreviewed scalar/flow/anchor forms; ignore indentation width/comments.
        This policy inspection is not a workflow validator or a data-leak proof.
        """
        self.assertNotIn("\t", text, "Tabs are outside the reviewed mapping shape")
        lines = textwrap.dedent("\n".join(line for line in text.splitlines()
                                         if not line.lstrip().startswith("#"))).splitlines()
        headers = []
        for index, line in enumerate(lines):
            if not line.strip() or line.lstrip().startswith("#") or line[0].isspace():
                continue
            match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)", line)
            self.assertIsNotNone(match, "Unreviewed workflow mapping syntax: " + line)
            key, value = match.groups()
            value = re.sub(r"\s+#.*$", "", value).strip()
            self.assertFalse(value.startswith(("&", "*", "!")), "Unreviewed YAML anchor, alias or tag")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            self.assertNotIn(key, [item[1] for item in headers], "Duplicate workflow key")
            headers.append((index, key, value))
        result = {}
        for n, (index, key, value) in enumerate(headers):
            end = headers[n + 1][0] if n + 1 < len(headers) else len(lines)
            body = textwrap.dedent("\n".join(lines[index + 1:end]))
            if value and value not in {"|", ">-"}:
                self.assertFalse(body.strip(), "Unreviewed multiline scalar: " + key)
            result[key] = (value, body)
        return result

    def _workflow_scalar(self, fields, key):
        self.assertIn(key, fields)
        value, body = fields[key]
        self.assertFalse(body.strip(), "Unexpected nested scalar: " + key)
        return value

    def _workflow_mapping(self, fields, key):
        self.assertIn(key, fields)
        self.assertEqual("", fields[key][0], "Expected reviewed block mapping: " + key)
        return self._workflow_fields(fields[key][1])

    def _workflow_steps(self, job):
        self.assertIn("steps", job)
        self.assertEqual("", job["steps"][0])
        lines = job["steps"][1].splitlines()
        starts = [n for n, line in enumerate(lines) if line.startswith("- ")]
        self.assertTrue(starts)
        self.assertTrue(all(not line.strip() or line.lstrip().startswith("#") for line in lines[:starts[0]]))
        steps = []
        for n, start in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(lines)
            steps.append(self._workflow_fields("\n".join(["  " + lines[start][2:]] + lines[start + 1:end])))
        return steps

    def _report_workflow_jobs(self, text, trigger="workflow_dispatch"):
        fields = self._workflow_fields(text)
        self.assertLessEqual(set(fields), {"name", "on", "permissions", "env", "jobs"})
        triggers = self._workflow_mapping(fields, "on")
        self.assertEqual({trigger}, set(triggers))
        self.assertEqual("", triggers[trigger][0])
        self.assertEqual({"contents": ("read", "")}, self._workflow_mapping(fields, "permissions"))
        self.assertEqual(1, len(re.findall(r"(?m)^\s*permissions\s*:", text)))
        self.assertNotRegex(text, r"\$\{\{\s*secrets(?:\.|\[)")
        self.assertNotRegex(text, r"(?m)^\s*(?:continue-on-error|environment|secrets)\s*:")
        self.assertNotRegex(text, r"(?i)\bgh\s+(?:release|workflow|api)\b|\bgit\s+(?:push|commit)\b")
        jobs = self._workflow_mapping(fields, "jobs")
        for name, value in jobs.items():
            self.assertEqual("", value[0], "Expected reviewed job block: " + name)
        parsed = {name: self._workflow_fields(value[1]) for name, value in jobs.items()}
        for job in parsed.values():
            checkouts = [step for step in self._workflow_steps(job)
                         if step.get("uses", ("", ""))[0].startswith("actions/checkout@")]
            self.assertEqual(1, len(checkouts))
            self.assertEqual("actions/checkout@v4", self._workflow_scalar(checkouts[0], "uses"))
            self.assertEqual({"persist-credentials": ("false", "")}, self._workflow_mapping(checkouts[0], "with"))
        return fields, parsed

    def _assert_report_upload(self, step, paths, condition="always()", timeout=None,
                              artifact_name="android-${{ env.RUNTIME_SCOPE }}-${{ github.run_id }}-${{ github.run_attempt }}"):
        keys = {"name", "if", "uses", "with"}
        if timeout is not None:
            keys.add("timeout-minutes")
            self.assertEqual(str(timeout), self._workflow_scalar(step, "timeout-minutes"))
        self.assertEqual(keys, set(step))
        self.assertEqual(REPORT_UPLOAD, self._workflow_scalar(step, "uses"))
        self.assertEqual(re.sub(r"\s+", "", condition), re.sub(r"\s+", "", self._workflow_scalar(step, "if")))
        options = self._workflow_mapping(step, "with")
        self.assertEqual({"name", "retention-days", "if-no-files-found", "path"}, set(options))
        self.assertEqual(artifact_name, self._workflow_scalar(options, "name"))
        self.assertEqual("1", self._workflow_scalar(options, "retention-days"))
        self.assertEqual("error", self._workflow_scalar(options, "if-no-files-found"))
        self.assertEqual("|", options["path"][0])
        self.assertEqual(paths, [line.strip() for line in options["path"][1].splitlines() if line.strip()])

    def _assert_android_runtime_report_policy(self, text):
        fields, jobs = self._report_workflow_jobs(text)
        self.assertEqual({"name", "on", "permissions", "env", "jobs"}, set(fields))
        env = self._workflow_mapping(fields, "env")
        self.assertEqual({"B02_CLASSES"}, set(env))
        self.assertEqual(",".join("gr.mastixa.manager." + name for name in (
            "CountryExtensionsTest", "CadastralM2MTest", "CadastralMigrationTest",
            "CadastralParcelRepositoryTest", "GreekCadastreDatasetTest", "CadastralUnionTest",
            "CadastreProvidersTest", "CadastralHardeningTest")), self._workflow_scalar(env, "B02_CLASSES"))
        dispatch = self._workflow_mapping(fields, "on")["workflow_dispatch"]
        scope = self._workflow_mapping(self._workflow_mapping(self._workflow_fields(dispatch[1]), "inputs"), "runtime_scope")
        self.assertEqual("choice", self._workflow_scalar(scope, "type"))
        self.assertRegex(self._workflow_scalar(scope, "options"), r"^\[\s*api36-full\s*,\s*api26-b02\s*\]$")
        self.assertEqual("api36-full", self._workflow_scalar(scope, "default"))
        self.assertEqual({"instrumentation", "b02-api26"}, set(jobs))
        for name, scope_name, api in (("instrumentation", "api36-full", "36"), ("b02-api26", "api26-b02", "26")):
            job = jobs[name]
            self.assertEqual({"if", "runs-on", "timeout-minutes", "env", "steps"}, set(job))
            self.assertEqual("ubuntu-latest", self._workflow_scalar(job, "runs-on"))
            self.assertEqual("45", self._workflow_scalar(job, "timeout-minutes"))
            self.assertEqual("${{inputs.runtime_scope=='" + scope_name + "'}}", re.sub(r"\s+", "", self._workflow_scalar(job, "if")))
            self.assertEqual({"RUNTIME_SCOPE": (scope_name, ""), "B02_ONLY": ("true" if api == "26" else "false", "")},
                             self._workflow_mapping(job, "env"))
            steps = self._workflow_steps(job)
            self.assertEqual(9, len(steps))
            self.assertEqual([
                "actions/checkout@v4", "actions/setup-java@v5", "android-actions/setup-android@v3",
                "gradle/actions/setup-gradle@v4", "reactivecircus/android-emulator-runner@v2", REPORT_UPLOAD,
            ], [self._workflow_scalar(step, "uses") for step in steps if "uses" in step])
            uploads = [step for step in steps if "upload-artifact" in step.get("uses", ("", ""))[0]]
            self.assertEqual(1, len(uploads))
            self._assert_report_upload(uploads[0], [
                "android/app/build/outputs/androidTest-results/connected/**/TEST-*.xml",
                "android/app/build/reports/androidTests/connected/checks/**",
                "${{ runner.temp }}/fieltra-runtime-summary/*.json",
                "${{ runner.temp }}/fieltra-runtime-summary/summary.txt",
            ])
            emulators = [step for step in steps if step.get("uses", ("", ""))[0] == "reactivecircus/android-emulator-runner@v2"]
            self.assertEqual(1, len(emulators))
            emulator = self._workflow_mapping(emulators[0], "with")
            self.assertEqual(api, self._workflow_scalar(emulator, "api-level"))
            self.assertEqual(api == "26", "android.testInstrumentationRunnerArguments.class=$B02_CLASSES" in self._workflow_scalar(emulator, "script"))
            scripts = "\n".join(step["run"][1] for step in steps if "run" in step)
            accounting = [step for step in steps if "actual.json" in step.get("run", ("", ""))[1]]
            self.assertEqual(1, len(accounting))
            self.assertEqual("always()", self._workflow_scalar(accounting[0], "if"))
            for guard in ("if not expected", "if not files:", "if duplicate or missing or unexpected:",
                          "if skipped - allowed_skips:", 'if counts["failed"]:', "if issues:", "raise SystemExit("):
                self.assertIn(guard, scripts)
        self.assertEqual(2, text.count("actions/upload-artifact@"))

    def _assert_windows_timeout_report_policy(self, text):
        fields, jobs = self._report_workflow_jobs(text, trigger="workflow_call")
        self.assertEqual({"name", "on", "permissions", "jobs"}, set(fields))
        self.assertEqual(("", ""), self._workflow_mapping(fields, "on")["workflow_call"])
        self.assertEqual({"diagnostics"}, set(jobs))
        job = jobs["diagnostics"]
        self.assertEqual({"runs-on", "timeout-minutes", "env", "steps"}, set(job))
        self.assertEqual("windows-latest", self._workflow_scalar(job, "runs-on"))
        self.assertEqual("50", self._workflow_scalar(job, "timeout-minutes"))
        env = self._workflow_mapping(job, "env")
        self.assertEqual({"QT_QPA_PLATFORM", "PYTHONUTF8", "MASTIXA_DATA_HOME", "FIELTRA_DIAGNOSTIC_OUTPUT"}, set(env))
        self.assertEqual("offscreen", self._workflow_scalar(env, "QT_QPA_PLATFORM"))
        self.assertEqual("1", self._workflow_scalar(env, "PYTHONUTF8"))
        for key, prefix in (("MASTIXA_DATA_HOME", "fieltra-timeout-home"), ("FIELTRA_DIAGNOSTIC_OUTPUT", "fieltra-windows-timeouts")):
            self.assertEqual("${{ runner.temp }}/" + prefix + "-${{ github.run_id }}-${{ github.run_attempt }}", self._workflow_scalar(env, key))
        steps = self._workflow_steps(job)
        self.assertEqual(6, len(steps))
        self.assertEqual(["actions/checkout@v4", "actions/setup-python@v5", REPORT_UPLOAD],
                         [step["uses"][0] for step in steps if "uses" in step])
        self.assertEqual({"uses", "with"}, set(steps[0]))
        self.assertEqual({"uses", "with"}, set(steps[1]))
        self.assertEqual({"persist-credentials": ("false", "")}, self._workflow_mapping(steps[0], "with"))
        self.assertEqual({"python-version": ("3.14", ""), "architecture": ("x64", "")}, self._workflow_mapping(steps[1], "with"))
        for step, timeout in ((steps[2], "15"), (steps[3], "25"), (steps[4], "2")):
            self.assertEqual("pwsh", self._workflow_scalar(step, "shell"))
            self.assertEqual(timeout, self._workflow_scalar(step, "timeout-minutes"))
        self.assertEqual("python -m pip install -r requirements-dev.txt -c requirements-windows-rc.txt", self._workflow_scalar(steps[2], "run"))
        self.assertEqual({"name", "timeout-minutes", "shell", "run"}, set(steps[2]))
        self.assertEqual({"name", "timeout-minutes", "shell", "run"}, set(steps[3]))
        self.assertEqual(">-", steps[3]["run"][0])
        self.assertEqual([
            "python", "tools/run_windows_tests.py", "--jobs", "1", "--timeout", "120",
            "--module-timeout", "tests.test_activity_expense_sync=240",
            "--module-timeout", "tests.test_stabilization=360",
            "--output", "$env:FIELTRA_DIAGNOSTIC_OUTPUT", *TIMEOUT_MODULES,
        ], shlex.split(steps[3]["run"][1]))
        evidence = steps[4]
        self.assertEqual({"name", "id", "if", "timeout-minutes", "shell", "run"}, set(evidence))
        self.assertEqual("evidence", self._workflow_scalar(evidence, "id"))
        self.assertEqual("always()", self._workflow_scalar(evidence, "if"))
        for guard in ('"results.json"', '"TIMEOUT"', '"exit_code"', '"elapsed_seconds"',
                      "len(set(names)) != 7", "set(names) != set(expected)", "upload_safe=", "if issues:", "raise SystemExit("):
            self.assertIn(guard, evidence["run"][1])
        self._assert_report_upload(steps[5], ["${{ env.FIELTRA_DIAGNOSTIC_OUTPUT }}/" + name
                                           for name in ("results.json", *(module + ".log" for module in TIMEOUT_MODULES))],
                                   "${{ always() && steps.evidence.outputs.upload_safe == 'true' }}", timeout=5,
                                   artifact_name="windows-timeouts-${{ github.run_id }}-${{ github.run_attempt }}")

    def test_reusable_windows_timeout_diagnostics_report_policy(self) -> None:
        self._assert_windows_timeout_report_policy(self._read(".github/workflows/windows-timeout-diagnostics.yml"))

    def _assert_verify_timeout_routing_policy(self, text):
        # Match the reviewed expressions, never evaluate arbitrary YAML or expressions.
        fields = self._workflow_fields(text)
        self.assertEqual({"name", "on", "permissions", "concurrency", "jobs"}, set(fields))
        triggers = self._workflow_mapping(fields, "on")
        self.assertEqual({"push", "pull_request", "workflow_dispatch"}, set(triggers))
        for event in ("push", "pull_request"):
            self.assertEqual(("", ""), triggers[event])
        dispatch = self._workflow_mapping(triggers, "workflow_dispatch")
        self.assertEqual({"inputs"}, set(dispatch))
        inputs = self._workflow_mapping(dispatch, "inputs")
        self.assertEqual({"scope"}, set(inputs))
        scope = self._workflow_mapping(inputs, "scope")
        self.assertEqual({"description", "type", "options", "default"}, set(scope))
        self.assertEqual("choice", self._workflow_scalar(scope, "type"))
        self.assertEqual("full", self._workflow_scalar(scope, "default"))
        self.assertRegex(self._workflow_scalar(scope, "options"),
                         r"^\[\s*full\s*,\s*maps\s*,\s*windows-timeouts\s*\]$")
        self.assertEqual({"contents": ("read", "")}, self._workflow_mapping(fields, "permissions"))
        self.assertNotRegex(text, r"(?m)^\s*(?:secrets|continue-on-error|environment)\s*:")
        self.assertNotRegex(text, r"\$\{\{\s*secrets(?:\.|\[)")
        self.assertNotIn("actions/upload-artifact", text)
        ordinary = "${{ github.event_name != 'workflow_dispatch' || inputs.scope != 'windows-timeouts' }}"
        diagnostic = "${{ github.event_name == 'workflow_dispatch' && inputs.scope == 'windows-timeouts' }}"
        concurrency = self._workflow_mapping(fields, "concurrency")
        self.assertEqual({"group", "cancel-in-progress"}, set(concurrency))
        self.assertEqual(
            "verify-${{ github.workflow }}-${{ github.ref }}"
            "${{ github.event_name == 'workflow_dispatch' && inputs.scope == 'windows-timeouts' && '-windows-timeouts' || '' }}",
            self._workflow_scalar(concurrency, "group"))
        self.assertEqual(ordinary, self._workflow_scalar(concurrency, "cancel-in-progress"))
        jobs = self._workflow_mapping(fields, "jobs")
        self.assertEqual({"source-audit", "windows", "android", "windows-timeouts"}, set(jobs))
        parsed = {name: self._workflow_mapping(jobs, name) for name in jobs}
        caller = parsed["windows-timeouts"]
        self.assertEqual({"if", "permissions", "uses"}, set(caller))
        self.assertEqual(diagnostic, self._workflow_scalar(caller, "if"))
        self.assertEqual({"contents": ("read", "")}, self._workflow_mapping(caller, "permissions"))
        self.assertEqual("./.github/workflows/windows-timeout-diagnostics.yml", self._workflow_scalar(caller, "uses"))
        for name, runner, limit in (("source-audit", "ubuntu-latest", "10"),
                                    ("windows", "windows-latest", "45"),
                                    ("android", "ubuntu-latest", "35")):
            job = parsed[name]
            self.assertEqual({"if", "runs-on", "timeout-minutes", "steps"} |
                             ({"env"} if name == "windows" else set()), set(job))
            condition = ("${{ inputs.scope != 'maps' && (github.event_name != 'workflow_dispatch' || "
                         "inputs.scope != 'windows-timeouts') }}" if name == "android" else ordinary)
            self.assertEqual(condition, self._workflow_scalar(job, "if"))
            self.assertEqual(runner, self._workflow_scalar(job, "runs-on"))
            self.assertEqual(limit, self._workflow_scalar(job, "timeout-minutes"))
        windows_steps = self._workflow_steps(parsed["windows"])
        commands = [step for step in windows_steps if "tools/run_windows_tests.py" in step.get("run", ("", ""))[1]]
        self.assertEqual(2, len(commands))
        full, maps = commands
        self.assertEqual("${{ inputs.scope != 'maps' }}", self._workflow_scalar(full, "if"))
        self.assertEqual("${{ inputs.scope == 'maps' }}", self._workflow_scalar(maps, "if"))
        self.assertEqual(
            ["python", "tools/run_windows_tests.py", "--jobs", "2", "--timeout", "120",
             "--module-timeout", "tests.test_activity_expense_sync=240",
             "--module-timeout", "tests.test_invoice_profile_ownership=360",
             "--module-timeout", "tests.test_phase16j_composed_ui_localization=180",
             "--module-timeout", "tests.test_sale_sources=360",
             "--module-timeout", "tests.test_stabilization=360"], shlex.split(full["run"][1]))
        self.assertEqual(
            ["python", "tools/run_windows_tests.py", "--jobs", "2", "--timeout", "120",
             "tests.test_satellite_maps", "tests.test_map_network", "tests.test_map_acceptance_ui",
             "tests.test_phase16j_map_ui", "tests.test_phase16j_ui_catalog", "tests.test_gis_ui",
             "tests.test_cadastral_presentation", "tests.test_kaek_lookup_ui",
             "tests.test_windows_legal_gate", "tests.test_windows_legal_selection"], shlex.split(maps["run"][1]))
        android_steps = self._workflow_steps(parsed["android"])
        jvm = [step for step in android_steps if "javac --release 17" in step.get("run", ("", ""))[1]]
        self.assertEqual(1, len(jvm))
        self.assertNotIn("if", jvm[0])
        self.assertIn("java -cp", jvm[0]["run"][1])
        build = [step for step in android_steps if "gradlew" in step.get("run", ("", ""))[0]]
        self.assertEqual(1, len(build))
        self.assertNotIn("if", build[0])
        self.assertEqual("android", self._workflow_scalar(build[0], "working-directory"))
        self.assertEqual("bash ./gradlew --no-daemon testDebugUnitTest lintDebug assembleDebug assembleChecksAndroidTest --console=plain",
                         self._workflow_scalar(build[0], "run"))

    def test_verify_routes_only_explicit_manual_scope_to_same_commit_diagnostics(self) -> None:
        self._assert_verify_timeout_routing_policy(self._read(".github/workflows/verify.yml"))

    def test_verify_timeout_routing_rejects_unsafe_mutations(self) -> None:
        original = self._read(".github/workflows/verify.yml")
        manual = "github.event_name == 'workflow_dispatch' && inputs.scope == 'windows-timeouts'"
        exclusion = "github.event_name != 'workflow_dispatch' || inputs.scope != 'windows-timeouts'"
        mutations = {
            "missing dispatch": original.replace("  workflow_dispatch:", "  workflow_call:", 1),
            "missing push": original.replace("  push:\n", "", 1),
            "missing PR": original.replace("  pull_request:\n", "", 1),
            "changed default": original.replace("default: full", "default: windows-timeouts", 1),
            "removed maps": original.replace("[full, maps, windows-timeouts]", "[full, windows-timeouts]", 1),
            "automatic diagnostic": original.replace("if: ${{ " + manual + " }}", "if: ${{ always() }}", 1),
            "shared cancellation group": original.replace("${{ " + manual + " && '-windows-timeouts' || '' }}", "", 1),
            "cancel running diagnostic": original.replace("cancel-in-progress: ${{ " + exclusion + " }}", "cancel-in-progress: true", 1),
            "unbounded diagnostic groups": original.replace("${{ github.ref }}", "${{ github.run_id }}", 1),
            "secrets inheritance": original.replace("  windows-timeouts:\n", "  windows-timeouts:\n    secrets: inherit\n", 1),
            "extra job": original + "\n  unreviewed:\n    uses: org/repo/.github/workflows/run.yml@main\n",
            "write permission": original.replace("contents: read", "contents: write", 1),
            "maps runs full suite": original.replace("if: ${{ inputs.scope != 'maps' }}", "if: ${{ always() }}", 1),
        }
        for name in ("source-audit", "windows"):
            mutations[name + " diagnostic leak"] = original.replace("  " + name + ":\n    if: ${{ " + exclusion + " }}",
                                                                   "  " + name + ":\n    if: ${{ always() }}", 1)
        mutations["android diagnostic leak"] = original.replace(
            "if: ${{ inputs.scope != 'maps' && (" + exclusion + ") }}", "if: ${{ inputs.scope != 'maps' }}", 1)
        reference = "./.github/workflows/windows-timeout-diagnostics.yml"
        for label, value in (("main reference", reference + "@main"),
                             ("development reference", reference + "@develop/v1.0.1"),
                             ("old commit reference", "Sxara242/Fieltra/" + reference[2:] + "@7219e7b36208398b9432111335c90c38c8f99685"),
                             ("remote reference", "org/repo/.github/workflows/diagnostics.yml@main")):
            mutations[label] = original.replace(reference, value, 1)
        for label, changed in mutations.items():
            with self.subTest(mutation=label):
                self.assertNotEqual(original, changed)
                with self.assertRaises(AssertionError):
                    self._assert_verify_timeout_routing_policy(changed)

    def test_manual_report_policies_reject_unsafe_mutations(self) -> None:
        # Only strings are changed: no workflow, test runner or subprocess executes here.
        for filename, check in (("android-runtime.yml", self._assert_android_runtime_report_policy),
                                ("windows-timeout-diagnostics.yml", self._assert_windows_timeout_report_policy)):
            original = self._read(".github/workflows/" + filename)
            trigger = "workflow_call" if filename == "windows-timeout-diagnostics.yml" else "workflow_dispatch"
            mutations = {
                "automatic trigger": original.replace("  " + trigger + ":", "  push:", 1),
                "additional automatic trigger": original.replace("  " + trigger + ":", "  push:\n  " + trigger + ":", 1),
                "PR trigger": original.replace("  " + trigger + ":", "  pull_request:", 1),
                "duplicate trigger": original.replace("  " + trigger + ":", "  " + trigger + ":\n  " + trigger + ":", 1),
                "flow trigger mapping": original.replace("on:\n  " + trigger + ":", "on: {" + trigger + ": null}", 1),
                "anchor mapping": original.replace("permissions:", "permissions: &token", 1),
                "write permission": original.replace("contents: read", "contents: write", 1),
                "privileged token": original.replace("contents: read", "contents: read\n  actions: write", 1),
                "long retention": original.replace("retention-days: 1", "retention-days: 7", 1),
                "unreviewed action": original.replace(REPORT_UPLOAD, "actions/upload-artifact@v4", 1),
                "persistent credentials": original.replace("persist-credentials: false", "persist-credentials: true", 1),
                "failure-only evidence lost": original.replace("if: always()", "if: success()", 1),
                "extra upload": original + "\n      - uses: " + REPORT_UPLOAD + "\n",
                "release action": original + "\n      - uses: softprops/action-gh-release@v2\n",
                "automatic rerun": original + "\n      - run: gh run rerun 123\n",
                "duplicate permissions": original + "\npermissions:\n  contents: write\n",
            }
            if filename == "windows-timeout-diagnostics.yml":
                mutations["direct dispatch"] = original.replace("  workflow_call:", "  workflow_dispatch:", 1)
                mutations["parallel workers"] = original.replace("--jobs 1", "--jobs 2", 1)
                mutations["raised limit"] = original.replace("tests.test_activity_expense_sync=240", "tests.test_activity_expense_sync=360", 1)
                mutations["raised default limit"] = original.replace("--timeout 120", "--timeout 240", 1)
                mutations["raised stabilization limit"] = original.replace("tests.test_stabilization=360", "tests.test_stabilization=480", 1)
                mutations["raised execution limit"] = original.replace("timeout-minutes: 25", "timeout-minutes: 30", 1)
                mutations["raised job limit"] = original.replace("timeout-minutes: 50", "timeout-minutes: 60", 1)
                mutations["extra module"] = original.replace("          tests.test_batch5_ui\n", "          tests.test_batch5_ui tests.test_unreviewed\n", 1)
                mutations["extra retry"] = original.replace("--jobs 1", "--jobs 1 --retries 2", 1)
                mutations["hidden failure"] = original.replace("        timeout-minutes: 25", "        continue-on-error: true\n        timeout-minutes: 25", 1)
                mutations["arbitrary reusable input"] = original.replace("  workflow_call:\n", "  workflow_call:\n    inputs:\n      command:\n        type: string\n", 1)
            else:
                mutations["unexpected B02 class"] = original.replace("gr.mastixa.manager.CadastralHardeningTest", "gr.mastixa.manager.OtherTest", 1)
            path = ("android/app/build/reports/androidTests/connected/checks/**" if filename == "android-runtime.yml"
                    else "${{ env.FIELTRA_DIAGNOSTIC_OUTPUT }}/results.json")
            for label, forbidden in (("workspace upload", "${{ github.workspace }}/**"),
                                     ("APK upload", "android/app/build/outputs/apk/debug/app-debug.apk"),
                                     ("installer upload", "dist/Fieltra-Setup.exe"),
                                     ("MSI upload", "dist/Fieltra.msi"),
                                     ("signing key upload", "android/release.keystore"),
                                     ("database upload", "data/mastixa_manager.db")):
                mutations[label] = original.replace(path, forbidden, 1)
            for label, changed in mutations.items():
                with self.subTest(workflow=filename, mutation=label):
                    self.assertNotEqual(original, changed)
                    with self.assertRaises(AssertionError):
                        check(changed)

    def test_release_builder_is_ci_usable_and_hashes_dynamic_version_installer(self) -> None:
        build = self._read("packaging/build_release.ps1")
        requirements = self._read("requirements-build.txt").strip()

        self.assertIn('[string]$PythonPath = ""', build)
        self.assertIn("-PythonPath <python.exe>", build)
        self.assertIn("MyAppVersion", build)
        self.assertIn('"Fieltra-$version-Setup.exe"', build)
        self.assertIn("Get-FileHash -Algorithm SHA256", build)
        self.assertEqual("PyInstaller==6.22.3\npyinstaller-hooks-contrib==2026.7", requirements)


if __name__ == "__main__":
    unittest.main()
