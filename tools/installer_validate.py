"""Opt-in installer cycle; preferences are observed, never protected by mutation.

Do not use the historical evidence harness. Execution requires a separately
authorized rebuilt candidate, its expected hash, and a fresh output directory.
Importing this file does not start validation or access the registry.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
PREFERENCE_KEY = r"Software\Mastixa\Mastixa Manager"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{B9B946A2-8711-4B35-9BCB-B40210E67357}_is1"
BLOCKED_INSTALLER_SHA256 = "ace3c4dbf470e19edbeef0eab62a7121af6890b809b461fe3d5cd778ecf6821e"
BLOCKED_INSTALLER_SHA256S = (
    BLOCKED_INSTALLER_SHA256,
    "50c2291c4d8765dbfb5479a3c17c2b8a909a763236cd45d799b29ebf1c988ce3",
)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_installer_identity(actual, expected):
    if actual in BLOCKED_INSTALLER_SHA256S:
        raise RuntimeError("Known-defective RC.2 installer refused; rebuild required")
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("A SHA256 from the separately reviewed rebuild is required")
    if actual != expected:
        raise RuntimeError("Installer differs from the reviewed rebuild hash")


def tree(path):
    return {str(p.relative_to(path)): digest(p) for p in path.rglob("*") if p.is_file()}


def reg_snapshot(key, registry):
    """Read values/types/subkeys deterministically; access errors must fail closed."""
    try:
        handle = registry.OpenKey(registry.HKEY_CURRENT_USER, key, 0, registry.KEY_READ)
    except FileNotFoundError:
        return None
    with handle:
        values = []
        children = {}
        index = 0
        while True:
            try:
                name, value, kind = registry.EnumValue(handle, index)
            except OSError as error:
                if error.winerror != 259:  # ERROR_NO_MORE_ITEMS, not access denied
                    raise
                break
            values.append([name, repr(value), kind])
            index += 1
        index = 0
        while True:
            try:
                name = registry.EnumKey(handle, index)
            except OSError as error:
                if error.winerror != 259:
                    raise
                break
            child = reg_snapshot(key + "\\" + name, registry)
            if child is None:
                raise RuntimeError("Registry changed during snapshot: " + key + "\\" + name)
            children[name] = child
            index += 1
        return {"values": sorted(values), "children": children}


def compare_preferences(before, after):
    return {"unchanged": before == after, "before": before, "after": after}


def shortcut_snapshot(paths):
    """Observe link bytes and timestamps without opening/saving shortcut objects."""
    snapshot = {}
    for path in paths:
        try:
            stat = path.stat()
        except FileNotFoundError:
            snapshot[str(path)] = None
        else:
            snapshot[str(path)] = {
                "sha256": digest(path), "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
    return snapshot


def compare_shortcuts(before, after):
    changed = sorted(path for path in before.keys() | after.keys()
                     if before.get(path) != after.get(path))
    return {"unchanged": before == after, "changed_paths": changed,
            "before": before, "after": after}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--expected-installer-sha256", required=True)
    parser.add_argument("--payload-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Execution is opt-in and requires separate owner authorization")
    # Refuse the known defective artifact before any registry access or file writes.
    installer = args.installer.resolve(strict=True)
    check_installer_identity(digest(installer), args.expected_installer_sha256.lower())
    payload = json.loads(args.payload_report.read_text(encoding="utf-8"))["payload_inventory"]
    out = args.output.resolve()
    if out.exists() or out.is_relative_to(ROOT):
        raise RuntimeError("Use a fresh evidence directory outside public source")
    elevation = subprocess.run([
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent())"
        ".IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)",
    ], capture_output=True, text=True, timeout=15, check=True)
    if elevation.stdout.strip().lower() != "false":
        raise RuntimeError("Ordinary-user execution required")
    import winreg  # No native registry module is imported during source inspection.
    if reg_snapshot(UNINSTALL_KEY, winreg) is not None:
        raise RuntimeError("Existing installer registration: do not replace")
    before = reg_snapshot(PREFERENCE_KEY, winreg)
    production = Path(os.environ["LOCALAPPDATA"]) / "Programs/Mastixa Manager"
    production_before = tree(production)
    shortcuts = [
        Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Mastixa Manager.lnk",
        Path(os.environ["USERPROFILE"]) / "Desktop/Mastixa Manager.lnk",
    ]
    shortcut_before = shortcut_snapshot(shortcuts)
    out.mkdir(parents=True, exist_ok=False)
    target = out / "install-rc"
    temp = out / "installer-temp"
    temp.mkdir()
    env = os.environ.copy()
    env.update(TEMP=str(temp), TMP=str(temp), MASTIXA_DATA_HOME=str(out / "installed-synthetic-data"))
    for name in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        env.pop(name, None)
    report = {
        "status": "RUNNING", "stages": [], "target": str(target),
        "installer_sha256": digest(installer),
        "preference_protection": "Read-only snapshots; no automatic restoration",
        "preference_before": before,
        "shortcut_protection": "/NOICONS; read-only snapshots; no automatic restoration",
        "shortcut_before": shortcut_before,
    }
    def save():
        with (out / "installer-progress.json").open("w", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    def check_state(label):
        comparison = compare_preferences(before, reg_snapshot(PREFERENCE_KEY, winreg))
        report.setdefault("preference_checks", []).append({"stage": label, **comparison})
        report["production_install_unchanged"] = tree(production) == production_before
        shortcut_comparison = compare_shortcuts(shortcut_before, shortcut_snapshot(shortcuts))
        report.setdefault("shortcut_checks", []).append({"stage": label, **shortcut_comparison})
        report["shortcuts_unchanged"] = shortcut_comparison["unchanged"]
        save()
        if not shortcut_comparison["unchanged"]:
            raise RuntimeError("/NOICONS shortcut state changed; stop without automatic restoration: "
                               + ", ".join(shortcut_comparison["changed_paths"]))
        if not all((comparison["unchanged"], report["production_install_unchanged"])):
            raise RuntimeError("Existing user state changed; stop without automatic restoration")
    def run(label, command, timeout, child_env=env):
        # Recheck before each process too, including concurrent external changes.
        check_state("before-" + label)
        report["stages"].append({"stage": label, "command": command, "status": "RUNNING"})
        save()
        result = subprocess.run(command, env=child_env, timeout=timeout, capture_output=True)
        (out / (label + "-stdout.log")).write_bytes(result.stdout)
        (out / (label + "-stderr.log")).write_bytes(result.stderr)
        report["stages"][-1].update(status="PASS" if result.returncode == 0 else "FAIL", exit=result.returncode)
        check_state(label)
        if result.returncode:
            raise RuntimeError(label + " failed: " + str(result.returncode))
    def install(label):
        run(label, [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-", "/NORESTART",
                    "/NOCLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS", "/NOICONS", "/TASKS=",
                    f"/DIR={target}", f"/LOG={out / (label + '.log')}"], 180)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_READ) as key:
            version = winreg.QueryValueEx(key, "DisplayVersion")[0]
            location = winreg.QueryValueEx(key, "InstallLocation")[0]
        if version != "1.0.0-rc.2" or Path(location).resolve() != target.resolve():
            raise RuntimeError("Unexpected installer registration")
        for item in payload:
            path = (target / item["path"]).resolve()
            if not path.is_relative_to(target.resolve()) or digest(path) != item["sha256"]:
                raise RuntimeError("Installed payload mismatch: " + item["path"])
    def uninstall(label):
        if target.is_symlink() or not target.resolve().is_relative_to(out):
            raise RuntimeError("Unexpected uninstall target")
        run(label, [str(target / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                    f"/LOG={out / (label + '.log')}"], 120)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and (reg_snapshot(UNINSTALL_KEY, winreg) is not None or target.exists()):
            time.sleep(0.2)
        if reg_snapshot(UNINSTALL_KEY, winreg) is not None or target.exists():
            raise RuntimeError("Uninstall did not remove the isolated installation")
    save()
    try:
        install("clean-install")
        marker = out / "installed-synthetic-data/owner-data-marker.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("Synthetic uninstall retention marker", encoding="utf-8")
        library = target / "_internal/PySide6/Qt6Core.dll"
        original_library = library.read_bytes()
        replacement = out / "synthetic-compatible-Qt6Core-replacement.dll"
        replacement.write_bytes(original_library + b"RC replacement retention test")
        library.write_bytes(replacement.read_bytes())
        install("repair")
        if library.read_bytes() != original_library:
            raise RuntimeError("Repair did not restore the supplier library")
        # Replacement is kept outside the installation and can be reapplied.
        library.write_bytes(replacement.read_bytes())
        if digest(library) != digest(replacement):
            raise RuntimeError("Compatible replacement cannot be reapplied")
        library.write_bytes(original_library)
        smoke_env = dict(env, QT_QPA_PLATFORM="offscreen", MASTIXA_SMOKE_OUTPUT=str(out / "installed-smoke.json"))
        run("installed-launch", [str(target / "MastixaManager.exe"), "--smoke-test"], 65, smoke_env)
        uninstall("uninstall-1")
        if not marker.exists():
            raise RuntimeError("Ordinary uninstall removed synthetic user data")
        install("reinstall")
        uninstall("uninstall-2")
        if not marker.exists():
            raise RuntimeError("Reinstall journey removed synthetic user data")
        check_state("final")
        report["status"] = "PASS"
    except Exception as error:
        report.update(status="BLOCKED", error=repr(error))
        # Observe after failure; never launch cleanup/uninstall or restore user state.
        try:
            check_state("failure")
        except Exception as observation_error:
            report["failure_observation_error"] = repr(observation_error)
        raise
    finally:
        save()
        (out / "installer-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
