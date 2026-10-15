"""Fail closed before RC packaging; also verify legal/resource output membership."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[1]


def configuration_errors(root=ROOT):
    errors = []
    errors.extend(runpy.run_path(str(root / "packaging/epsg_provenance.py"))["configuration_errors"](root))
    config = json.loads((root / "packaging/windows-rc.json").read_text(encoding="utf-8"))
    version = runpy.run_path(str(root / "app/version.py"))
    for key, symbol in (("version", "APP_VERSION"), ("channel", "RELEASE_CHANNEL"),
                        ("product", "APP_NAME"), ("license", "APP_LICENSE")):
        if config[key] != version[symbol]:
            errors.append(f"Release metadata mismatch: {key}")
    text = (root / "LICENSE").read_text(encoding="utf-8")
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in text or "13. Remote Network Interaction" not in text:
        errors.append("Full AGPL license is missing")
    manifest = json.loads((root / "licenses/manifest.json").read_text(encoding="utf-8"))
    try:
        runpy.run_path(str(root / "packaging/legal_inputs.py"))["legal_data_entries"](root)
    except (ValueError, OSError, KeyError) as exc:
        errors.append(f"Legal selection invalid: {exc}")
    for item in manifest["texts"] + manifest.get("attributions", []):
        path = root / item["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            errors.append(f"License text missing/changed: {item['path']}")
    ledger = json.loads((root / "docs/asset-provenance.json").read_text(encoding="utf-8"))
    expected = {p.relative_to(root).as_posix() for p in (root / "app/assets").rglob("*") if p.is_file()}
    expected.add("packaging/mastixa_manager.ico")
    if {x["path"] for x in ledger} != expected:
        errors.append("Resource provenance inventory is incomplete")
    for item in ledger:
        path = root / item["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            errors.append(f"Resource missing/changed: {item['path']}")
        if item["category"] == "UNKNOWN PROVENANCE":
            errors.append(f"Unknown shipping provenance: {item['path']}")
    return errors


def legal_readiness_errors(config):
    """Require affirmative legal gates; audit/reproduction scores are informational."""
    errors = []
    gates = config.get("distribution_legal_gates", {})
    for name in ("B1", "B2", "B3", "B4", "B5"):
        gate = gates.get(name, {})
        if gate.get("legal_status") != "PASS":
            errors.append(f"{name}-LEGAL: {gate.get('reason', 'Missing affirmative legal clearance')}")
    if not config["native_notices_complete"] or not config["corresponding_source_ready"]:
        errors.extend(config["blockers"] or ["Native notices/source delivery not verified"])
    return errors


def preflight_errors(root=ROOT):
    errors = configuration_errors(root)
    config = json.loads((root / "packaging/windows-rc.json").read_text(encoding="utf-8"))
    return errors + legal_readiness_errors(config)


def require_ready(root=ROOT):
    errors = preflight_errors(root)
    if errors:
        raise RuntimeError("BLOCKED BEFORE RC BUILD\n" + "\n".join(errors))


def bundle_errors(bundle, root=ROOT):
    errors = []
    errors.extend(runpy.run_path(str(root / "packaging/epsg_provenance.py"))["bundle_errors"](bundle, root))
    errors.extend(runpy.run_path(str(root / "packaging/mesa_policy.py"))["bundle_errors"](bundle))
    excluded = runpy.run_path(str(root / "packaging/qt_exclusions.py"))["excluded_windows_file"]
    internal = bundle / "_internal"
    manifest = json.loads((root / "licenses/manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["texts"] + manifest.get("attributions", []) if item.get("shipping", True)}
    paths.update({"LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/manifest.json", "DISTRIBUTION_SOURCE.md",
                  "SOURCE_DELIVERY_PLAN.md", "source-artifacts.json",
                  "updates/staging/rc.json", "updates/staging/stable.json"})
    for name in sorted(paths):
        source = root / ("docs/" + name if name in {"DISTRIBUTION_SOURCE.md", "SOURCE_DELIVERY_PLAN.md", "source-artifacts.json"} else name)
        target = internal / name
        if not target.is_file() or source.read_bytes() != target.read_bytes():
            errors.append(f"Packaged legal/feed file missing/changed: {name}")
    excluded_legal = {item['path'] for item in manifest['texts'] + manifest.get('attributions', [])
                      if not item.get('shipping', True)}
    for name in sorted(excluded_legal):
        if (internal / name).is_file():
            errors.append(f"Nonshipping legal material in bundle: {name}")
    for path in bundle.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(bundle).as_posix()
        lower = relative.casefold()
        if "virtualkeyboard" in lower:
            errors.append(f"Forbidden Qt VirtualKeyboard: {relative}")
        elif excluded(relative):
            errors.append(f"Forbidden excluded Windows component/resource: {relative}")
        if any(part.casefold() in {"data", "backups", "profile_trash", "logs"} for part in path.relative_to(bundle).parts):
            errors.append(f"Private/local directory in bundle: {relative}")
        if path.suffix.casefold() in {".db", ".sqlite", ".sqlite3", ".mastixaprofile", ".fieltraprofile", ".pfx", ".pem", ".key"}:
            if not ((path.name.casefold() == "proj.db" and "pyproj" in lower.split("/"))
                    or lower == "_internal/certifi/cacert.pem"):
                errors.append(f"Private/unapproved resource in bundle: {relative}")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configuration-only", action="store_true")
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    problems = bundle_errors(args.bundle) if args.bundle else (
        configuration_errors() if args.configuration_only else preflight_errors())
    print("\n".join(problems) if problems else "PASS")
    raise SystemExit(1 if problems else 0)
