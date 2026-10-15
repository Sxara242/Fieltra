"""Read-only RC2 source verifier; external assets are mandatory and hash checked."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe(root, name):
    p = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts:
        raise ValueError('Unsafe package path')
    target = (root / Path(*p.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Path escapes package')
    return target


def verify(root, assets=None):
    manifest = json.loads((root / 'RECIPIENT_MANIFEST.json').read_text(encoding='utf-8'))
    external = {a['materialized_path']: a for a in manifest['external_assets']}
    expected, local = {}, set()
    for row in manifest['files']:
        name = row['path']
        if name.casefold() in {n.casefold() for n in expected}:
            raise ValueError('Duplicate package path')
        expected[name] = row['sha256']
        p = safe(root, name)
        if name in external and not p.exists():
            if assets is None:
                raise ValueError('Required separate source asset missing: ' + name)
            p = safe(assets, external[name]['filename'])
        else:
            local.add(name)
        if not p.is_file() or p.stat().st_size != row['size'] or digest(p) != row['sha256']:
            raise ValueError('Missing/changed source material: ' + name)
        if name in external:
            a = external[name]
            if a['sha256'] != row['sha256'] or a['size'] != row['size']:
                raise ValueError('External asset index mismatch')
    if set(external) - set(expected):
        raise ValueError('Unindexed external asset')
    for record in (manifest['application_source'], manifest['installer_repack_source']):
        with zipfile.ZipFile(safe(root, record['path'])) as z:
            members = [i.filename for i in z.infolist() if not i.is_dir()]
            if len({n.casefold() for n in members}) != len(members) or set(members) != set(record['members_sha256']):
                raise ValueError('Source ZIP membership mismatch')
            for name in members:
                safe(root, name)
                if hashlib.sha256(z.read(name)).hexdigest() != record['members_sha256'][name]:
                    raise ValueError('Source ZIP member changed')
    expected['RECIPIENT_MANIFEST.json'] = digest(root / 'RECIPIENT_MANIFEST.json')
    lines = (root / 'SHA256SUMS').read_text(encoding='utf-8').splitlines()
    pairs = [line.split('  ', 1) for line in lines]
    if len({n for h, n in pairs}) != len(pairs) or {n: h for h, n in pairs} != expected:
        raise ValueError('Checksum index mismatch')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != local | {'RECIPIENT_MANIFEST.json', 'SHA256SUMS'}:
        raise ValueError('Unexpected package files')
    return {'result': 'PASS', 'source_material_files': len(manifest['files']),
            'external_assets': len(external), 'application_members': len(manifest['application_source']['members_sha256']),
            'scope': 'Offline source bytes only; no install, build, network or acceptance'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    p.add_argument('--assets', type=Path)
    args = p.parse_args()
    try:
        print(json.dumps(verify(args.root, args.assets)))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        p.exit(1, 'FAIL: ' + str(error) + '\n')
