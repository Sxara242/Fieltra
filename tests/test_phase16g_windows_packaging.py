from __future__ import annotations

from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from app.runtime_paths import resolve_base_dir


ROOT = Path(__file__).resolve().parents[1]


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
            "-ExecutablePath", str(ROOT / "nonexistent-smoke-bundle" / "MastixaManager.exe"),
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
            exe = root / "MastixaManager.exe"
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

    def test_release_versions_are_consistent(self) -> None:
        readme = self._read("README.md")
        version_module = self._read("app/version.py")
        iss = self._read("installer/MastixaManager.iss")
        version_info = self._read("packaging/version_info.txt")

        readme_match = re.search(r"Current Windows source targets \*\*([^*]+)\*\*", readme)
        module_match = re.search(r'^APP_VERSION = "([^"]+)"', version_module, re.MULTILINE)
        iss_match = re.search(r'^#define MyAppVersion "([^"]+)"', iss, re.MULTILINE)
        file_match = re.search(r"StringStruct\('FileVersion', '([^']+)'\)", version_info)
        product_match = re.search(r"StringStruct\('ProductVersion', '([^']+)'\)", version_info)

        for match in (
            readme_match,
            module_match,
            iss_match,
            file_match,
            product_match,
        ):
            self.assertIsNotNone(match)

        versions = {
            readme_match.group(1),
            module_match.group(1),
            iss_match.group(1),
            file_match.group(1),
            product_match.group(1),
        }
        self.assertEqual(1, len(versions), f"Release versions drifted: {sorted(versions)}")

    def test_installer_upgrade_contract_preserves_external_user_data(self) -> None:
        iss = self._read("installer/MastixaManager.iss")

        self.assertIn("AppId={{B9B946A2-8711-4B35-9BCB-B40210E67357}", iss)
        self.assertIn("PrivilegesRequired=lowest", iss)
        self.assertIn("DefaultDirName={%LOCALAPPDATA}\\Programs\\Mastixa Manager", iss)
        self.assertNotIn("MastixaManager\\data", iss)
        self.assertNotIn("MastixaManager\\backups", iss)

        data_dir = resolve_base_dir(
            frozen=True,
            environ={"LOCALAPPDATA": "C:/SyntheticProfiles/test/AppData/Local"},
        )
        install_dir = Path("C:/SyntheticProfiles/test/AppData/Local/Programs/Mastixa Manager").resolve()
        self.assertEqual(
            Path("C:/SyntheticProfiles/test/AppData/Local/MastixaManager").resolve(),
            data_dir,
        )
        self.assertNotEqual(install_dir, data_dir)
        self.assertNotIn(install_dir, data_dir.parents)

    def test_uninstaller_preserves_preferences_and_removes_install_residue(self) -> None:
        iss = self._read("installer/MastixaManager.iss")

        self.assertNotIn("[Registry]", iss)
        self.assertNotIn("uninsdeletekey", iss)
        self.assertIn("RegDeleteKeyIncludingSubkeys(HKCU, 'Software\\Mastixa\\Mastixa Manager')", iss)
        self.assertNotIn("Microsoft\\Windows\\CurrentVersion\\UFH\\SHC", iss)

        self.assertIn("[UninstallDelete]", iss)
        self.assertIn('Type: filesandordirs; Name: "{app}"', iss)
        self.assertNotIn(
            'Type: filesandordirs; Name: "{%LOCALAPPDATA}\\MastixaManager"',
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

    def test_release_output_is_isolated_and_retries_transient_windows_locks(self) -> None:
        build = self._read("packaging/build_release.ps1")
        ci_build = self._read("packaging/ci_windows_release.ps1")
        workflow = self._read(".github/workflows/windows-release-gate.yml")

        self.assertIn('[string]$InstallerOutputDir = ""', build)
        self.assertIn("[int]$InstallerBuildAttempts = 3", build)
        self.assertIn('$outputArg = "/O$installerOutput"', build)
        self.assertIn("for ($attempt = 1; $attempt -le $InstallerBuildAttempts; $attempt++)", build)
        self.assertIn("Retrying in $delaySeconds seconds", build)
        self.assertIn('$outputDir = Join-Path $env:RUNNER_TEMP', ci_build)
        self.assertIn('$env:GITHUB_RUN_ID', ci_build)
        self.assertIn('$env:GITHUB_RUN_ATTEMPT', ci_build)
        self.assertIn("-InstallerOutputDir $outputDir", ci_build)
        self.assertIn("-InstallerBuildAttempts 3", ci_build)
        self.assertNotIn("ci_windows_release.ps1", workflow)
        self.assertNotIn('dist\\installer\\MastixaManager-', workflow)

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
        for name in ("verify.yml", "windows-release-gate.yml", "android-runtime.yml"):
            self.assertNotIn("actions/upload-artifact", self._read(".github/workflows/" + name))
        workflow = self._read(".github/workflows/android-update-gate.yml")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("  push:", workflow)
        self.assertIn("if: ${{ inputs.upload_apk }}", workflow)
        self.assertIn("retention-days: 1", workflow)

    def test_release_builder_is_ci_usable_and_hashes_dynamic_version_installer(self) -> None:
        build = self._read("packaging/build_release.ps1")
        requirements = self._read("requirements-build.txt").strip()

        self.assertIn('[string]$PythonPath = ""', build)
        self.assertIn("-PythonPath <python.exe>", build)
        self.assertIn("MyAppVersion", build)
        self.assertIn('"MastixaManager-$version-Setup.exe"', build)
        self.assertIn("Get-FileHash -Algorithm SHA256", build)
        self.assertEqual("PyInstaller==6.22.3\npyinstaller-hooks-contrib==2026.7", requirements)


if __name__ == "__main__":
    unittest.main()
