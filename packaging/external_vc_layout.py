"""Copy a qualified frozen payload unchanged behind a separately audited launcher.

Never executes an application/installer or installs/downloads a runtime. The
complete original payload remains intact; all outputs must be fresh paths.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from crt_policy import is_crt, verify_bundle
from launcher_audit import audit_launcher


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_files(root):
    root = Path(root)
    if not root.is_dir():
        raise ValueError('Frozen payload directory does not exist')
    for ancestor in (root, *root.parents):
        if ancestor.is_symlink() or ancestor.is_junction():
            raise ValueError('Reparse input/output ancestor refused')
    result = {}
    pending = [root]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                path = Path(entry.path)
                if entry.is_symlink() or getattr(entry.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400:
                    raise ValueError('Reparse payload member refused')
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    relative = path.relative_to(root).as_posix()
                    if is_crt(path.name) or path.name.casefold().startswith('vc_redist'):
                        raise ValueError('Microsoft runtime payload forbidden: ' + relative)
                    result[relative] = digest(path)
    return result


def create_layout(payload, launcher, output, expected=None):
    payload, launcher, output = Path(payload).absolute(), Path(launcher).absolute(), Path(output).absolute()
    if output.exists() or output.is_relative_to(payload):
        raise ValueError('Fresh output outside the original payload required')
    for ancestor in (output, *output.parents):
        if ancestor.is_symlink() or ancestor.is_junction():
            raise ValueError('Reparse output ancestor refused')
    config = json.loads((ROOT / 'packaging/windows-prerequisite.json').read_text())
    if config['mode'] != 'external-launch' or config['payload_directory'] != 'engine':
        raise ValueError('Only the approved external-launch layout is active')
    original = safe_files(payload)
    if expected is not None and original != expected:
        raise ValueError('Frozen payload differs from the retained manifest')
    if 'MastixaManager.exe' not in original:
        raise ValueError('Frozen application executable is missing')
    verify_bundle(payload, ROOT)
    audit = audit_launcher(launcher)
    output.mkdir(parents=True)
    shutil.copytree(payload, output / 'engine')
    shutil.copyfile(launcher, output / 'MastixaManager.exe')
    copied = safe_files(output / 'engine')
    if copied != original or safe_files(payload) != original:
        raise ValueError('Original/copied frozen member identities changed')
    if digest(output / 'MastixaManager.exe') != audit['sha256']:
        raise ValueError('Launcher changed during staging')
    return {'mode': 'external-launch', 'frozen_members': len(original),
            'frozen_members_sha256': original, 'launcher': audit,
            'layout_members_sha256': safe_files(output),
            'original_payload_unchanged': True, 'runtime_bundled': False,
            'app_or_installer_executed': False,
            'logical_installed_payload_bytes': sum(p.stat().st_size for p in output.rglob('*') if p.is_file())}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-manifest', type=Path)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads(args.expected_manifest.read_text()) if args.expected_manifest else None
    if args.receipt.exists():
        raise ValueError('Fresh receipt required')
    receipt = create_layout(args.payload, args.launcher, args.output, expected)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in receipt.items() if not k.endswith('sha256')}, indent=2))
