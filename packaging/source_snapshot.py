"""Create a deterministic, private-data-free Windows source candidate.

This is a local retention artifact. It is not a corresponding-source approval
or a written source offer; the release gate remains authoritative.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = frozenset({
    'main.py', 'run.bat', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'README.md',
    'CONTRIBUTING.md', 'CHANGELOG.md', 'requirements.txt',
    'requirements-build.txt', 'requirements-dev.txt', 'requirements-windows-rc.txt',
    'requirements-windows-rc-hashed.txt',
})
TREES = frozenset({'app', 'packaging', 'installer', 'licenses', 'tests', 'tools', 'shared', '.github'})
SUFFIXES = frozenset({'.py', '.json', '.sql', '.txt', '.md', '.rst', '.html',
                     '.png', '.ico', '.svg', '.qss', '.spec', '.ps1', '.iss', '.isl',
                     '.bat', '.ui', '.ts', '.qm', '.csv', '.toml', '.yaml', '.yml',
                     '.c', '.h', '.rc', '.manifest'})
PRIVATE_PARTS = frozenset({'data', 'backups', 'logs', 'profile_trash',
                           '__pycache__', '.git', '.env', 'secrets'})
PRIVATE_SUFFIXES = frozenset({'.db', '.sqlite', '.sqlite3', '.mastixaprofile',
                              '.pem', '.pfx', '.p12', '.key', '.log', '.pyc'})

def source_files(root=ROOT):
    root = Path(root).resolve()
    names = subprocess.check_output([
        'git', '-c', f'safe.directory={root.as_posix()}', '-C', str(root),
        'ls-files', '--cached', '--others', '--exclude-standard', '-z',
    ]).decode('utf-8').split('\0')
    selected = []
    for name in sorted(set(names) - {''}):
        path = root / name
        parts = path.relative_to(root).parts
        if any(part.casefold() in PRIVATE_PARTS for part in parts) or path.suffix.lower() in PRIVATE_SUFFIXES:
            continue
        allowed = name in ROOT_FILES or (
            parts[0] in TREES and (path.suffix.lower() in SUFFIXES or parts[0] == 'licenses')
        ) or (parts[0] == 'docs' and path.suffix.lower() in {'.md', '.json'}) or (
            name in {'updates/staging/rc.json', 'updates/staging/stable.json'}
        )
        if not allowed or not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f'Unsafe source path: {name}')
        selected.append((name, path.read_bytes()))
    if not {'main.py', 'LICENSE', 'packaging/MastixaManager.spec'} <= {n for n, _ in selected}:
        raise ValueError('Required Windows source inputs are missing')
    return selected

def create_snapshot(output, root=ROOT):
    output = Path(output).resolve()
    root = Path(root).resolve()
    if output.is_relative_to(root):
        raise ValueError('Write source candidate outside the checkout to avoid self inclusion')
    rows = source_files(root)
    inventory = {name: hashlib.sha256(data).hexdigest() for name, data in rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in rows:
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return {'kind': 'LOCAL PREBUILD SOURCE CANDIDATE; final artifact binding pending',
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'size': output.stat().st_size, 'files': inventory,
            'privacy': 'Explicit Windows roots/extensions; no owner database, backups, logs, credentials, Git metadata or evidence directories',
            'public_source_published': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    receipt = create_snapshot(args.output)
    args.output.with_suffix('.receipt.json').write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Retained {len(receipt['files'])} source files; SHA256 {receipt['sha256']}")
