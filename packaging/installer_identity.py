"""Content-addressed installer identity and explicit same-release ancestry.

Names, clocks and Git HEADs are not build ordering. Retained predecessor receipts
establish ordering; changing a file name never changes identity or precedence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def version_key(version):
    match = re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(alpha|beta|rc)\.(0|[1-9]\d*))?', version)
    if not match:
        return None
    major, minor, patch, phase, serial = match.groups()
    parts = [int(major), int(minor), int(patch), {None: 3, 'alpha': 0, 'beta': 1, 'rc': 2}[phase], int(serial or 0)]
    return tuple(parts) if max(parts) <= 999999 else None


def classify(existing, installed_version, installed_id, installed_ancestors,
             incoming_version, incoming_id, incoming_ancestors):
    if not existing:
        return 'install'
    old, new = version_key(installed_version), version_key(incoming_version)
    if old is None or new is None:
        return 'review'
    if old < new:
        return 'upgrade'
    if old > new:
        return 'downgrade'
    if not installed_id:
        return 'review'
    if installed_id == incoming_id:
        return 'repair'
    if installed_id in incoming_ancestors:
        return 'upgrade'
    if incoming_id in installed_ancestors:
        return 'downgrade'
    return 'review'


def legacy_builds():
    return json.loads((ROOT / 'packaging/installer_legacy_builds.json').read_text())['builds']


def identify_legacy(version, files):
    for build in legacy_builds():
        if version == build['version'] and all(files.get(name) == sha for name, sha in build['files'].items()):
            return build['id']
    return ''


def create_identity(layout_members, version, predecessors=(), compiler=None):
    if version_key(version) is None:
        raise ValueError('Unsupported release version')
    ancestors = {build['id'] for build in legacy_builds() if build['version'] == version}
    for receipt in predecessors:
        if hashlib.sha256(canonical(receipt['inputs'])).hexdigest() != receipt['id']:
            raise ValueError('Predecessor content identity does not match its receipt')
        if receipt['inputs']['version'] != version:
            raise ValueError('Build ancestry is only required within the same release version')
        ancestors.add(receipt['id'])
        ancestors.update(receipt['inputs']['ancestors'])
    source = {}
    for name in ('installer/MastixaManager.iss', 'installer/maintenance_identity.iss',
                 'installer/Greek.isl', 'packaging/mastixa_manager.ico', 'LICENSE',
                 'packaging/installer_legacy_builds.json'):
        source[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    inputs = {'schema': 1, 'version': version, 'ancestors': sorted(ancestors),
              'layout_members': layout_members, 'installer_inputs': source}
    if compiler:
        directory = Path(compiler).parent
        inputs['compiler_inputs'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.iterdir()) if p.is_file() and
            p.suffix.lower() in {'.exe', '.dll', '.e32', '.e64', '.isl', '.iss', '.ico', '.bmp'}
            and not p.name.lower().startswith('unins')}
    return {'id': hashlib.sha256(canonical(inputs)).hexdigest(), 'inputs': inputs}


def inno_defines(identity):
    return ('#define MyBuildId "' + identity['id'] + '"\n' +
            '#define MyBuildAncestors "|' + '|'.join(identity['inputs']['ancestors']) + '|"\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout-receipt', type=Path)
    parser.add_argument('--payload', type=Path)
    parser.add_argument('--launcher', type=Path)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--predecessor', type=Path, action='append', default=[])
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix('.iss').exists():
        raise ValueError('Fresh identity receipt required')
    if args.layout_receipt:
        members = json.loads(args.layout_receipt.read_text())['layout_members_sha256']
    else:
        from external_vc_layout import safe_files, digest
        members = {'engine/' + name: sha for name, sha in safe_files(args.payload).items()}
        members['Fieltra.exe'] = digest(args.launcher)
    identity = create_identity(members, args.version,
                               [json.loads(p.read_text()) for p in args.predecessor], args.compiler)
    args.output.write_text(json.dumps(identity, indent=2) + '\n', encoding='utf-8')
    args.output.with_suffix('.iss').write_text(inno_defines(identity), encoding='utf-8')
    print(identity['id'])
